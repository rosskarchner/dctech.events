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
import time
from datetime import datetime

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

    # Set createdAt if not present
    if 'createdAt' not in event_data:
        event_data['createdAt'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    item = {
        'PK': f'EVENT#{guid}',
        'SK': 'META',
        'source': 'manual',
        'status': 'ACTIVE',
        **{k: v for k, v in event_data.items() if v is not None},
    }

    if date:
        item['GSI1PK'] = f'DATE#{date}'
        item['GSI1SK'] = f'TIME#{time_val}' if time_val else 'TIME#'

    categories = event_data.get('categories', [])
    if categories:
        item['GSI2PK'] = f'CATEGORY#{categories[0]}'
        item['GSI2SK'] = f'DATE#{date}'

    # GSI3: createdAt queries
    created_at = item.get('createdAt', '')
    if created_at:
        month_key = created_at[:7]
        item['GSI3PK'] = f'CREATED#{month_key}'
        item['GSI3SK'] = created_at

    # GSI4: date-range queries
    if date:
        item['GSI4PK'] = 'EVT#ACTIVE'
        item['GSI4SK'] = f'{date}#{time_val}' if time_val else date

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


# ─── GSI4 EVENT queries (consolidated table) ──────────────────────

def get_future_events():
    """
    Get all active events with date >= today via GSI4.

    GSI4PK: EVT#ACTIVE, GSI4SK: {date}#{time}
    Returns list of event dicts sorted by date/time.
    """
    table = _get_table()
    today = datetime.now().strftime('%Y-%m-%d')

    items = []
    try:
        response = table.query(
            IndexName='GSI4',
            KeyConditionExpression=Key('GSI4PK').eq('EVT#ACTIVE') & Key('GSI4SK').gte(today),
        )
        items.extend(response.get('Items', []))
        while 'LastEvaluatedKey' in response:
            response = table.query(
                IndexName='GSI4',
                KeyConditionExpression=Key('GSI4PK').eq('EVT#ACTIVE') & Key('GSI4SK').gte(today),
                ExclusiveStartKey=response['LastEvaluatedKey'],
            )
            items.extend(response.get('Items', []))
    except ClientError as e:
        print(f"Error querying GSI4 for future events: {e}")
        return []

    events = [_dynamo_item_to_event_full(item) for item in items]
    events.sort(key=lambda x: (str(x.get('date', '')), str(x.get('time', ''))))
    return events


def get_recently_added(limit=50):
    """
    Get recently added events via GSI3 CREATED# partition.

    GSI3PK: CREATED#{YYYY-MM}, GSI3SK: {createdAt_iso}
    Queries the current month (and previous month for good coverage).
    Returns list of event dicts sorted by createdAt descending.
    """
    table = _get_table()
    now = datetime.now()
    items = []

    # Query current month and previous month
    months_to_query = [now.strftime('%Y-%m')]
    if now.month == 1:
        months_to_query.append(f'{now.year - 1}-12')
    else:
        months_to_query.append(f'{now.year}-{now.month - 1:02d}')

    try:
        for month_key in months_to_query:
            response = table.query(
                IndexName='GSI3',
                KeyConditionExpression=Key('GSI3PK').eq(f'CREATED#{month_key}'),
                ScanIndexForward=False,
                Limit=limit,
            )
            items.extend(response.get('Items', []))
    except ClientError as e:
        print(f"Error querying GSI3 for recently added: {e}")
        return []

    # Sort by createdAt descending and limit
    items.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
    items = items[:limit]

    return [_dynamo_item_to_event_full(item) for item in items]


def _dynamo_item_to_event_full(item):
    """Convert a DynamoDB EVENT item to a full event dict (for site rendering)."""
    guid = item['PK'].split('#', 1)[1]
    event = {'guid': guid, 'id': guid, 'eventId': guid}

    for field in ['title', 'date', 'time', 'end_date', 'end_time',
                  'location', 'url', 'cost', 'description', 'group',
                  'group_website', 'categories', 'source', 'submitted_by',
                  'submitter_link', 'start_date', 'start_time',
                  'duplicate_of', 'hidden', 'city', 'state',
                  'location_type', 'also_published_by', 'createdAt',
                  'overrides', 'status']:
        if field in item:
            event[field] = item[field]

    return event


def put_ical_event(guid, data):
    """
    Write an iCal EVENT entity to the config table.

    Preserves overridden fields (tracked in the 'overrides' map) and createdAt.
    Sets GSI4 keys for date-range queries and GSI3 keys for createdAt queries.

    Args:
        guid: Event GUID (MD5 hash)
        data: Event data dict
    """
    table = _get_table()

    # Check for existing event to preserve overridden fields and createdAt
    existing = table.get_item(Key={'PK': f'EVENT#{guid}', 'SK': 'META'}).get('Item')

    overrides_map = {}
    if existing:
        overrides_map = existing.get('overrides', {})
        # Preserve createdAt from existing
        if 'createdAt' not in data and 'createdAt' in existing:
            data['createdAt'] = existing['createdAt']
        # Preserve overridden fields
        for field, is_overridden in overrides_map.items():
            if is_overridden and field in existing:
                data[field] = existing[field]

    if 'createdAt' not in data:
        data['createdAt'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    date_val = data.get('date', '')
    time_val = data.get('time', '')

    item = {
        'PK': f'EVENT#{guid}',
        'SK': 'META',
        'source': 'ical',
        'status': 'ACTIVE',
        **{k: v for k, v in data.items() if v is not None},
    }

    # Preserve overrides map
    if overrides_map:
        item['overrides'] = overrides_map

    # GSI1: date-based queries (existing pattern)
    if date_val:
        item['GSI1PK'] = f'DATE#{date_val}'
        item['GSI1SK'] = f'TIME#{time_val}' if time_val else 'TIME#'

    # GSI2: category queries
    categories = data.get('categories', [])
    if categories:
        item['GSI2PK'] = f'CATEGORY#{categories[0]}'
        item['GSI2SK'] = f'DATE#{date_val}'

    # GSI3: createdAt queries
    created_at = data.get('createdAt', '')
    if created_at:
        month_key = created_at[:7]  # YYYY-MM
        item['GSI3PK'] = f'CREATED#{month_key}'
        item['GSI3SK'] = created_at

    # GSI4: date-range queries for active events
    if date_val:
        item['GSI4PK'] = 'EVT#ACTIVE'
        item['GSI4SK'] = f'{date_val}#{time_val}' if time_val else date_val

    table.put_item(Item=item)
