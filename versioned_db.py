"""
Versioned DynamoDB write wrapper.

Provides wiki-style change tracking by snapshotting the previous state
before any mutation. History entries are co-located with the entity:

    PK: EVENT#{guid}   SK: V#{iso_timestamp}

Each history entry contains: snapshot (full previous state), editor, reason,
timestamp, and optional ttl.

Usage:
    from versioned_db import versioned_put, versioned_delete, get_history, rollback

    versioned_put('EVENT#abc123', item, editor='admin@example.com', reason='Fixed title')
    history = get_history('EVENT#abc123', limit=10)
    rollback('EVENT#abc123', '2026-02-23T15:30:00Z', editor='admin@example.com')
"""

import os
import copy
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

CONFIG_TABLE_NAME = os.environ.get('CONFIG_TABLE_NAME', 'dctech-events')

_table = None
_client = None


def _get_table():
    """Get or create DynamoDB table resource."""
    global _table
    if _table is None:
        dynamodb = boto3.resource('dynamodb')
        _table = dynamodb.Table(CONFIG_TABLE_NAME)
    return _table


def _get_client():
    """Get or create DynamoDB client (for TransactWriteItems)."""
    global _client
    if _client is None:
        _client = boto3.client('dynamodb')
    return _client


def _now_iso():
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def _serialize_for_transact(item):
    """Convert a high-level dict to DynamoDB JSON format for TransactWriteItems."""
    from boto3.dynamodb.types import TypeSerializer
    serializer = TypeSerializer()
    return {k: serializer.serialize(v) for k, v in item.items()}


def _deserialize_from_dynamo(dynamo_json):
    """Convert DynamoDB JSON format back to high-level dict."""
    from boto3.dynamodb.types import TypeDeserializer
    deserializer = TypeDeserializer()
    return {k: deserializer.deserialize(v) for k, v in dynamo_json.items()}


def versioned_put(pk, item, editor, reason, sk='META', ttl=None):
    """
    Write an item with automatic history snapshot.

    If the item already exists, the previous state is saved as a V# history
    entry before the new state is written. Both operations happen atomically
    via TransactWriteItems.

    If the item doesn't exist yet, it's written directly (no history needed).

    Args:
        pk: Partition key value (e.g. 'EVENT#abc123')
        item: Complete item dict to write (must include all fields).
              PK and SK will be set automatically.
        editor: Who made this change (email, system name, etc.)
        reason: Why the change was made
        sk: Sort key for the main item (default 'META')
        ttl: Optional TTL epoch for the history entry
    """
    table = _get_table()
    client = _get_client()
    table_name = table.table_name
    timestamp = _now_iso()

    # Read current state
    existing = table.get_item(Key={'PK': pk, 'SK': sk}).get('Item')

    # Build the new item
    new_item = {**item, 'PK': pk, 'SK': sk}

    if existing is None:
        # No prior version — just write directly
        table.put_item(Item=new_item)
        return

    # Build history entry from previous state
    history_item = {
        'PK': pk,
        'SK': f'V#{timestamp}',
        'snapshot': existing,
        'editor': editor,
        'reason': reason,
        'timestamp': timestamp,
    }
    if ttl is not None:
        history_item['ttl'] = ttl

    # Transactional write: history + update
    transact_items = [
        {
            'Put': {
                'TableName': table_name,
                'Item': _serialize_for_transact(history_item),
            }
        },
        {
            'Put': {
                'TableName': table_name,
                'Item': _serialize_for_transact(new_item),
            }
        },
    ]

    try:
        client.transact_write_items(TransactItems=transact_items)
    except ClientError as e:
        if e.response['Error']['Code'] == 'TransactionCanceledException':
            reasons = e.response.get('CancellationReasons', [])
            raise RuntimeError(
                f"Versioned put transaction failed for {pk}: {reasons}"
            ) from e
        raise


def versioned_delete(pk, editor, reason, sk='META', ttl=None):
    """
    Soft-delete an item with history snapshot.

    Saves the current state as a V# history entry, then updates the META
    item with status='DELETED' and deleted_at timestamp. The item is NOT
    physically removed — it can be restored via rollback().

    Args:
        pk: Partition key value
        editor: Who made this change
        reason: Why the item was deleted
        sk: Sort key (default 'META')
        ttl: Optional TTL epoch for the history entry
    """
    table = _get_table()
    client = _get_client()
    table_name = table.table_name
    timestamp = _now_iso()

    # Read current state
    existing = table.get_item(Key={'PK': pk, 'SK': sk}).get('Item')
    if existing is None:
        return  # Nothing to delete

    # Build history entry
    history_item = {
        'PK': pk,
        'SK': f'V#{timestamp}',
        'snapshot': existing,
        'editor': editor,
        'reason': reason,
        'timestamp': timestamp,
    }
    if ttl is not None:
        history_item['ttl'] = ttl

    # Build soft-deleted item (preserve PK/SK, strip GSI keys, mark deleted)
    deleted_item = {
        'PK': pk,
        'SK': sk,
        'status': 'DELETED',
        'deleted_at': timestamp,
        'deleted_by': editor,
        'delete_reason': reason,
    }

    transact_items = [
        {
            'Put': {
                'TableName': table_name,
                'Item': _serialize_for_transact(history_item),
            }
        },
        {
            'Put': {
                'TableName': table_name,
                'Item': _serialize_for_transact(deleted_item),
            }
        },
    ]

    try:
        client.transact_write_items(TransactItems=transact_items)
    except ClientError as e:
        if e.response['Error']['Code'] == 'TransactionCanceledException':
            reasons = e.response.get('CancellationReasons', [])
            raise RuntimeError(
                f"Versioned delete transaction failed for {pk}: {reasons}"
            ) from e
        raise


def get_history(pk, limit=20):
    """
    Get change history for an entity.

    Queries all V# sort keys under the given PK, returning newest first.

    Args:
        pk: Partition key value (e.g. 'EVENT#abc123')
        limit: Max number of history entries to return

    Returns:
        List of history entry dicts, newest first. Each contains:
        - snapshot: The full previous state
        - editor: Who made the change
        - reason: Why the change was made
        - timestamp: When the change happened
    """
    table = _get_table()

    response = table.query(
        KeyConditionExpression=Key('PK').eq(pk) & Key('SK').begins_with('V#'),
        ScanIndexForward=False,  # newest first
        Limit=limit,
    )

    entries = response.get('Items', [])

    # Handle pagination if we haven't hit the limit
    while 'LastEvaluatedKey' in response and len(entries) < limit:
        response = table.query(
            KeyConditionExpression=Key('PK').eq(pk) & Key('SK').begins_with('V#'),
            ScanIndexForward=False,
            Limit=limit - len(entries),
            ExclusiveStartKey=response['LastEvaluatedKey'],
        )
        entries.extend(response.get('Items', []))

    return entries


def rollback(pk, version_ts, editor, sk='META'):
    """
    Restore an entity to a previous version.

    Reads the snapshot from the specified V# history entry and writes it
    back as the current META item, creating a new history entry for the
    rollback itself.

    Args:
        pk: Partition key value
        version_ts: ISO timestamp of the version to restore (the V# SK suffix)
        editor: Who is performing the rollback
        sk: Sort key (default 'META')

    Raises:
        ValueError: If the specified version doesn't exist
    """
    table = _get_table()

    # Find the requested version
    version_sk = f'V#{version_ts}'
    response = table.get_item(Key={'PK': pk, 'SK': version_sk})
    version_entry = response.get('Item')

    if version_entry is None:
        raise ValueError(f"Version {version_ts} not found for {pk}")

    snapshot = version_entry.get('snapshot')
    if snapshot is None:
        raise ValueError(f"Version {version_ts} has no snapshot for {pk}")

    # The snapshot IS the complete item — write it back via versioned_put
    # This creates a new history entry for the rollback
    restored_item = dict(snapshot)
    # Remove PK/SK from the item dict since versioned_put sets them
    restored_item.pop('PK', None)
    restored_item.pop('SK', None)

    versioned_put(
        pk=pk,
        item=restored_item,
        editor=editor,
        reason=f'Rollback to version {version_ts}',
        sk=sk,
    )


def reset_clients():
    """Reset cached clients (useful for testing)."""
    global _table, _client
    _table = None
    _client = None
