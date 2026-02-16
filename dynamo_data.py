"""
DynamoDB Data Access Layer for the config table (dctech-events).

Provides the same interfaces as YAML file reads, enabling gradual
migration from YAML-based CMS to DynamoDB single-table design.

Feature flag: Set USE_DYNAMO_DATA=1 env var to enable DynamoDB reads.
When disabled, falls back to YAML file reads for local development.

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
import glob as globmod
import yaml
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

# Feature flag for gradual cutover
USE_DYNAMO_DATA = os.environ.get('USE_DYNAMO_DATA', '0') == '1'

# Config table name
CONFIG_TABLE_NAME = os.environ.get('CONFIG_TABLE_NAME', 'dctech-events')

# YAML fallback paths
GROUPS_DIR = '_groups'
CATEGORIES_DIR = '_categories'
SINGLE_EVENTS_DIR = '_single_events'
EVENT_OVERRIDES_DIR = '_event_overrides'

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
    Get all groups. Replaces YAML _groups/*.yaml reads.

    Returns:
        List of group dictionaries, each with 'id' field.
    """
    if not USE_DYNAMO_DATA:
        return _get_groups_from_yaml()

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
        return _get_groups_from_yaml()

    return groups


def get_active_groups():
    """Get only active groups, sorted by name."""
    if not USE_DYNAMO_DATA:
        groups = _get_groups_from_yaml()
        return [g for g in groups if g.get('active', True)]

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
        groups = _get_groups_from_yaml()
        return [g for g in groups if g.get('active', True)]

    groups.sort(key=lambda x: x.get('name', '').lower())
    return groups


def _dynamo_item_to_group(item):
    """Convert a DynamoDB GROUP item to group dict matching YAML format."""
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


def _get_groups_from_yaml():
    """Fallback: load groups from YAML files."""
    groups = []
    for file_path in globmod.glob(os.path.join(GROUPS_DIR, '*.yaml')):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                group = yaml.safe_load(f)
                group['id'] = os.path.splitext(os.path.basename(file_path))[0]
                groups.append(group)
        except Exception as e:
            print(f"Error loading group from {file_path}: {e}")
    return groups


# ─── CATEGORY operations ────────────────────────────────────────────

def get_all_categories():
    """
    Get all categories. Replaces YAML _categories/*.yaml reads.

    Returns:
        Dict mapping category slug to category metadata.
    """
    if not USE_DYNAMO_DATA:
        return _get_categories_from_yaml()

    table = _get_table()
    categories = {}

    try:
        # Scan for all CATEGORY entities (small dataset, scan is fine)
        response = table.scan(
            FilterExpression=Key('PK').begins_with('CATEGORY#') & Key('SK').eq('META'),
        )
        items = response.get('Items', [])
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                FilterExpression=Key('PK').begins_with('CATEGORY#') & Key('SK').eq('META'),
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
        return _get_categories_from_yaml()

    return categories


def _get_categories_from_yaml():
    """Fallback: load categories from YAML files."""
    categories = {}
    for file_path in globmod.glob(os.path.join(CATEGORIES_DIR, '*.yaml')):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                category = yaml.safe_load(f)
                slug = os.path.splitext(os.path.basename(file_path))[0]
                category['slug'] = slug
                categories[slug] = category
        except Exception as e:
            print(f"Error loading category from {file_path}: {e}")
    return categories


# ─── SINGLE EVENT operations ────────────────────────────────────────

def get_single_events():
    """
    Get all manually-submitted single events. Replaces _single_events/*.yaml reads.

    Returns:
        List of event dictionaries.
    """
    if not USE_DYNAMO_DATA:
        return _get_single_events_from_yaml()

    table = _get_table()
    events = []

    try:
        # Scan for EVENT entities with source=manual
        response = table.scan(
            FilterExpression=Key('PK').begins_with('EVENT#') & Key('SK').eq('META'),
        )
        items = response.get('Items', [])
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                FilterExpression=Key('PK').begins_with('EVENT#') & Key('SK').eq('META'),
                ExclusiveStartKey=response['LastEvaluatedKey'],
            )
            items.extend(response.get('Items', []))

        for item in items:
            if item.get('source') == 'manual':
                events.append(_dynamo_item_to_event(item))

    except ClientError as e:
        print(f"Error fetching single events from DynamoDB: {e}")
        return _get_single_events_from_yaml()

    return events


def _dynamo_item_to_event(item):
    """Convert a DynamoDB EVENT item to event dict matching YAML format."""
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


def _get_single_events_from_yaml():
    """Fallback: load single events from YAML files."""
    events = []
    for file_path in globmod.glob(os.path.join(SINGLE_EVENTS_DIR, '*.yaml')):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                event = yaml.safe_load(f)
                event['id'] = os.path.splitext(os.path.basename(file_path))[0]
                events.append(event)
        except Exception as e:
            print(f"Error loading event from {file_path}: {e}")
    return events


# ─── EVENT OVERRIDE operations ──────────────────────────────────────

def get_event_override(guid):
    """
    Get an event override by GUID. Replaces _event_overrides/{guid}.yaml reads.

    Args:
        guid: MD5 hash identifying the event

    Returns:
        Override dict or None if no override exists.
    """
    if not USE_DYNAMO_DATA:
        return _get_override_from_yaml(guid)

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
        return _get_override_from_yaml(guid)

    return None


def _get_override_from_yaml(guid):
    """Fallback: load event override from YAML file."""
    override_file = os.path.join(EVENT_OVERRIDES_DIR, f"{guid}.yaml")
    if os.path.exists(override_file):
        try:
            with open(override_file, 'r', encoding='utf-8') as f:
                override = yaml.safe_load(f)
                return override if override else None
        except Exception as e:
            print(f"Error loading override from {override_file}: {e}")
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
