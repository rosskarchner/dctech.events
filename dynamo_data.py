"""
DynamoDB Data Access Layer for the config table (dctech-events).

Provides interfaces for reading and writing site configuration and content
from the single-table DynamoDB design.

Entity key patterns:
| Entity     | PK                  | SK   | GSI1PK          | GSI1SK         | GSI2PK           | GSI2SK          |
|------------|---------------------|------|-----------------|----------------|------------------|-----------------|
| GROUP      | GROUP#{slug}        | META | ACTIVE#{0|1}    | NAME#{name}    | CATEGORY#{cat}   | GROUP#{slug}    |
| CATEGORY   | CATEGORY#{slug}     | META | —               | —              | —                | —               |
| EVENT      | EVENT#{guid}        | META | DATE#{date}     | TIME#{time}    | CATEGORY#{cat}   | DATE#{date}     |
| OVERRIDE   | OVERRIDE#{guid}     | META | —               | —              | —                | —               |
| DRAFT      | DRAFT#{id}          | META | STATUS#{status} | {created_at}   | —                | —               |
| ICAL_CACHE | ICAL#{group_id}     | EVENT#{guid} | —       | —              | —                | —               |
| ICAL_META  | ICAL_META#{group_id}| META | —               | —              | —                | —               |
"""

import os
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

# Config table name
CONFIG_TABLE_NAME = os.environ.get('CONFIG_TABLE_NAME', 'dctech-events')

_table = None


def _get_table():
    """Get or create DynamoDB table resource."""
    global _table
    if _table is None:
        dynamodb = boto3.resource('dynamodb')
        _table = dynamodb.Table(CONFIG_TABLE_NAME)
    return _table


# ─── GROUP operations ───────────────────────────────────────────────

def get_all_groups():
    """
    Get all groups from DynamoDB.

    Returns:
        List of group dictionaries, each with 'id' field.
    """
    table = _get_table()
    groups = []

    # Query GSI1 for active groups: GSI1PK = ACTIVE#1
    try:
        response = table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq('ACTIVE#1'),
        )
        items = response.get('Items', [])
        while 'LastEvaluatedKey' in response:
            response = table.query(
                IndexName='GSI1',
                KeyConditionExpression=Key('GSI1PK').eq('ACTIVE#1'),
                ExclusiveStartKey=response['LastEvaluatedKey'],
            )
            items.extend(response.get('Items', []))

        # Also get inactive groups
        response = table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq('ACTIVE#0'),
        )
        items.extend(response.get('Items', []))
        while 'LastEvaluatedKey' in response:
            response = table.query(
                IndexName='GSI1',
                KeyConditionExpression=Key('GSI1PK').eq('ACTIVE#0'),
                ExclusiveStartKey=response['LastEvaluatedKey'],
            )
            items.extend(response.get('Items', []))

        for item in items:
            groups.append(_dynamo_item_to_group(item))

    except ClientError as e:
        print(f"Error fetching groups from DynamoDB: {e}")
        return []

    return groups


def get_active_groups():
    """Get only active groups from DynamoDB, sorted by name."""
    table = _get_table()
    groups = []

    try:
        response = table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq('ACTIVE#1'),
        )
        items = response.get('Items', [])
        while 'LastEvaluatedKey' in response:
            response = table.query(
                IndexName='GSI1',
                KeyConditionExpression=Key('GSI1PK').eq('ACTIVE#1'),
                ExclusiveStartKey=response['LastEvaluatedKey'],
            )
            items.extend(response.get('Items', []))

        for item in items:
            groups.append(_dynamo_item_to_group(item))

    except ClientError as e:
        print(f"Error fetching active groups from DynamoDB: {e}")
        return []

    groups.sort(key=lambda x: x.get('name', '').lower())
    return groups


def _dynamo_item_to_group(item):
    """Convert a DynamoDB GROUP item to group dict."""
    # PK is GROUP#{slug}
    slug = item['PK'].split('#', 1)[1]
    group = {
        'id': slug,
        'name': item.get('name', ''),
        'active': item.get('active', True),
    }
    # Copy optional fields
    for field in ['website', 'ical', 'fallback_url', 'categories',
                  'suppress_urls', 'suppress_guid', 'scan_for_metadata',
                  'url_override']:
        if field in item:
            group[field] = item[field]

    return group


# ─── CATEGORY operations ────────────────────────────────────────────

def get_all_categories():
    """
    Get all categories from DynamoDB.

    Returns:
        Dict mapping category slug to category metadata.
    """
    table = _get_table()
    categories = {}

    try:
        # Scan for all CATEGORY entities (small dataset, scan is fine)
        response = table.scan(
            FilterExpression=Attr('PK').begins_with('CATEGORY#') & Attr('SK').eq('META'),
        )
        items = response.get('Items', [])
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                FilterExpression=Attr('PK').begins_with('CATEGORY#') & Attr('SK').eq('META'),
                ExclusiveStartKey=response['LastEvaluatedKey'],
            )
            items.extend(response.get('Items', []))

        for item in items:
            slug = item['PK'].split('#', 1)[1]
            categories[slug] = {
                'slug': slug,
                'name': item.get('name', ''),
                'description': item.get('description', ''),
            }

    except ClientError as e:
        print(f"Error fetching categories from DynamoDB: {e}")
        return {}

    return categories


# ─── SINGLE EVENT operations ────────────────────────────────────────

def get_single_events():
    """
    Get all manually-submitted single events from DynamoDB.

    Returns:
        List of event dictionaries.
    """
    table = _get_table()
    events = []

    try:
        # Scan for EVENT entities with source=manual or source=submitted
        response = table.scan(
            FilterExpression=Attr('PK').begins_with('EVENT#') & Attr('SK').eq('META'),
        )
        items = response.get('Items', [])
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                FilterExpression=Attr('PK').begins_with('EVENT#') & Attr('SK').eq('META'),
                ExclusiveStartKey=response['LastEvaluatedKey'],
            )
            items.extend(response.get('Items', []))

        for item in items:
            if item.get('source') in ('manual', 'submitted'):
                events.append(_dynamo_item_to_event(item))

    except ClientError as e:
        print(f"Error fetching single events from DynamoDB: {e}")
        return []

    return events


def _dynamo_item_to_event(item):
    """Convert a DynamoDB EVENT item to event dict."""
    guid = item['PK'].split('#', 1)[1]
    event = {'guid': guid, 'id': guid}

    # Copy all relevant fields
    for field in ['title', 'date', 'time', 'end_date', 'end_time',
                  'location', 'url', 'cost', 'description', 'group',
                  'group_website', 'categories', 'source', 'submitted_by',
                  'submitter_link', 'start_date', 'start_time',
                  'duplicate_of', 'hidden']:
        if field in item:
            event[field] = item[field]

    return event


# ─── EVENT OVERRIDE operations ──────────────────────────────────────

def get_event_override(guid):
    """
    Get an event override by GUID from DynamoDB.

    Args:
        guid: MD5 hash identifying the event

    Returns:
        Override dict or None if no override exists.
    """
    table = _get_table()

    try:
        response = table.get_item(
            Key={'PK': f'OVERRIDE#{guid}', 'SK': 'META'},
        )
        item = response.get('Item')
        if item:
            override = {}
            for field in ['categories', 'edited_by', 'title', 'url',
                          'location', 'time', 'hidden', 'duplicate_of']:
                if field in item:
                    override[field] = item[field]
            return override if override else None

    except ClientError as e:
        print(f"Error fetching override from DynamoDB: {e}")
        return None

    return None


# ─── WRITE operations (for migration and admin) ────────────────────

def put_group(slug, group_data):
    """Write a GROUP entity to the config table."""
    table = _get_table()
    active = group_data.get('active', True)
    name = group_data.get('name', '')

    item = {
        'PK': f'GROUP#{slug}',
        'SK': 'META',
        'GSI1PK': f'ACTIVE#{1 if active else 0}',
        'GSI1SK': f'NAME#{name}',
        **{k: v for k, v in group_data.items() if v is not None},
    }

    # Set GSI2 for first category (if any)
    categories = group_data.get('categories', [])
    if categories:
        item['GSI2PK'] = f'CATEGORY#{categories[0]}'
        item['GSI2SK'] = f'GROUP#{slug}'

    table.put_item(Item=item)


def put_category(slug, category_data):
    """Write a CATEGORY entity to the config table."""
    table = _get_table()
    item = {
        'PK': f'CATEGORY#{slug}',
        'SK': 'META',
        **{k: v for k, v in category_data.items() if v is not None},
    }
    table.put_item(Item=item)


def put_single_event(guid, event_data):
    """Write a single EVENT entity to the config table."""
    table = _get_table()
    date = event_data.get('date', '')
    time_val = event_data.get('time', '')

    item = {
        'PK': f'EVENT#{guid}',
        'SK': 'META',
        'source': 'manual',
        **{k: v for k, v in event_data.items() if v is not None},
    }

    if date:
        item['GSI1PK'] = f'DATE#{date}'
        item['GSI1SK'] = f'TIME#{time_val}' if time_val else 'TIME#'

    categories = event_data.get('categories', [])
    if categories:
        item['GSI2PK'] = f'CATEGORY#{categories[0]}'
        item['GSI2SK'] = f'DATE#{date}'

    table.put_item(Item=item)


def put_override(guid, override_data):
    """Write an OVERRIDE entity to the config table."""
    table = _get_table()
    item = {
        'PK': f'OVERRIDE#{guid}',
        'SK': 'META',
        **{k: v for k, v in override_data.items() if v is not None},
    }
    table.put_item(Item=item)
