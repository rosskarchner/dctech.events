"""
DynamoDB CRUD operations for the config table (dctech-events).

Used by the API backend for admin and submission workflows.
"""

import os
import time
import uuid
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key, Attr

CONFIG_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'dctech-events')
MATERIALIZED_TABLE_NAME = os.environ.get('MATERIALIZED_TABLE_NAME', 'DcTechEvents')

_table = None
_materialized_table = None


def _get_table():
    global _table
    if _table is None:
        dynamodb = boto3.resource('dynamodb')
        _table = dynamodb.Table(CONFIG_TABLE_NAME)
    return _table


def _get_materialized_table():
    global _materialized_table
    if _materialized_table is None:
        dynamodb = boto3.resource('dynamodb')
        _materialized_table = dynamodb.Table(MATERIALIZED_TABLE_NAME)
    return _materialized_table


# ─── DRAFT operations ─────────────────────────────────────────────

def create_draft(draft_type, data, submitter_email):
    """Create a new DRAFT entity (pending submission)."""
    table = _get_table()
    draft_id = str(uuid.uuid4())[:8]
    now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    item = {
        'PK': f'DRAFT#{draft_id}',
        'SK': 'META',
        'GSI1PK': 'STATUS#pending',
        'GSI1SK': now,
        'draft_type': draft_type,
        'submitter_email': submitter_email,
        'created_at': now,
        'status': 'pending',
        **{k: v for k, v in data.items() if v is not None},
    }

    table.put_item(Item=item)
    return draft_id


def get_drafts_by_status(status='pending'):
    """Get all drafts with a given status."""
    table = _get_table()
    items = []

    response = table.query(
        IndexName='GSI1',
        KeyConditionExpression=Key('GSI1PK').eq(f'STATUS#{status}'),
        ScanIndexForward=False,
    )
    items.extend(response.get('Items', []))
    while 'LastEvaluatedKey' in response:
        response = table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq(f'STATUS#{status}'),
            ExclusiveStartKey=response['LastEvaluatedKey'],
            ScanIndexForward=False,
        )
        items.extend(response.get('Items', []))

    return [_draft_item_to_dict(item) for item in items]


def get_drafts_by_submitter(submitter_email):
    """Get all drafts submitted by a specific user."""
    table = _get_table()
    items = []

    response = table.scan(
        FilterExpression=Attr('PK').begins_with('DRAFT#') & Attr('SK').eq('META') & Attr('submitter_email').eq(submitter_email),
    )
    items.extend(response.get('Items', []))
    while 'LastEvaluatedKey' in response:
        response = table.scan(
            FilterExpression=Attr('PK').begins_with('DRAFT#') & Attr('SK').eq('META') & Attr('submitter_email').eq(submitter_email),
            ExclusiveStartKey=response['LastEvaluatedKey'],
        )
        items.extend(response.get('Items', []))

    drafts = [_draft_item_to_dict(item) for item in items]
    drafts.sort(key=lambda d: d.get('created_at', ''), reverse=True)
    return drafts


def get_draft(draft_id):
    """Get a single draft by ID."""
    table = _get_table()
    response = table.get_item(Key={'PK': f'DRAFT#{draft_id}', 'SK': 'META'})
    item = response.get('Item')
    return _draft_item_to_dict(item) if item else None


def update_draft_status(draft_id, new_status, reviewer_email=None):
    """Update draft status (approve/reject)."""
    table = _get_table()
    now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    update_expr = 'SET #status = :status, GSI1PK = :gsi1pk, updated_at = :now'
    expr_values = {
        ':status': new_status,
        ':gsi1pk': f'STATUS#{new_status}',
        ':now': now,
    }
    expr_names = {'#status': 'status'}

    if reviewer_email:
        update_expr += ', reviewer_email = :reviewer'
        expr_values[':reviewer'] = reviewer_email

    table.update_item(
        Key={'PK': f'DRAFT#{draft_id}', 'SK': 'META'},
        UpdateExpression=update_expr,
        ExpressionAttributeValues=expr_values,
        ExpressionAttributeNames=expr_names,
    )


def _draft_item_to_dict(item):
    """Convert a DynamoDB DRAFT item to a dict."""
    draft_id = item['PK'].split('#', 1)[1]
    result = {'id': draft_id}
    for field in ['draft_type', 'status', 'submitter_email', 'reviewer_email',
                  'created_at', 'updated_at', 'title', 'date', 'time',
                  'location', 'url', 'cost', 'description', 'group_name',
                  'name', 'website', 'ical', 'categories']:
        if field in item:
            val = item[field]
            result[field] = float(val) if isinstance(val, Decimal) else val
    return result


# ─── GROUP operations ──────────────────────────────────────────────

def get_all_groups():
    """Get all groups (active and inactive)."""
    table = _get_table()
    items = []

    for active_flag in ['ACTIVE#1', 'ACTIVE#0']:
        response = table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq(active_flag),
        )
        items.extend(response.get('Items', []))
        while 'LastEvaluatedKey' in response:
            response = table.query(
                IndexName='GSI1',
                KeyConditionExpression=Key('GSI1PK').eq(active_flag),
                ExclusiveStartKey=response['LastEvaluatedKey'],
            )
            items.extend(response.get('Items', []))

    return [_group_item_to_dict(item) for item in items]


def get_group(slug):
    """Get a single group by slug."""
    table = _get_table()
    response = table.get_item(Key={'PK': f'GROUP#{slug}', 'SK': 'META'})
    item = response.get('Item')
    return _group_item_to_dict(item) if item else None


def put_group(slug, data):
    """Create or update a GROUP entity."""
    table = _get_table()
    active = data.get('active', True)
    name = data.get('name', '')

    item = {
        'PK': f'GROUP#{slug}',
        'SK': 'META',
        'GSI1PK': f'ACTIVE#{1 if active else 0}',
        'GSI1SK': f'NAME#{name}',
        **{k: v for k, v in data.items() if v is not None},
    }

    categories = data.get('categories', [])
    if categories:
        item['GSI2PK'] = f'CATEGORY#{categories[0]}'
        item['GSI2SK'] = f'GROUP#{slug}'

    table.put_item(Item=item)


def _group_item_to_dict(item):
    """Convert a DynamoDB GROUP item to a dict."""
    slug = item['PK'].split('#', 1)[1]
    group = {'id': slug, 'name': item.get('name', ''), 'active': item.get('active', True)}
    for field in ['website', 'ical', 'fallback_url', 'categories',
                  'suppress_urls', 'suppress_guid', 'scan_for_metadata', 'url_override']:
        if field in item:
            group[field] = item[field]
    return group


# ─── EVENT operations ──────────────────────────────────────────────

def get_events_by_date(date_prefix=None):
    """Get events, optionally filtered by date prefix (e.g. '2026-02')."""
    table = _get_table()
    items = []

    # GSI1PK stores full dates like DATE#2026-02-19, so we scan with a filter
    # for prefix matching (begins_with is not supported on partition keys in queries)
    scan_kwargs = {
        'FilterExpression': Attr('PK').begins_with('EVENT#') & Attr('SK').eq('META'),
    }
    if date_prefix:
        scan_kwargs['FilterExpression'] = (
            Attr('GSI1PK').begins_with(f'DATE#{date_prefix}') & Attr('SK').eq('META')
        )

    response = table.scan(**scan_kwargs)
    items.extend(response.get('Items', []))
    while 'LastEvaluatedKey' in response:
        scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
        response = table.scan(**scan_kwargs)
        items.extend(response.get('Items', []))

    return [_event_item_to_dict(item) for item in items]


def _event_item_to_dict(item):
    """Convert a DynamoDB EVENT item to a dict."""
    guid = item['PK'].split('#', 1)[1]
    event = {'guid': guid, 'id': guid}
    for field in ['title', 'date', 'time', 'end_date', 'end_time',
                  'location', 'url', 'cost', 'description', 'group',
                  'group_website', 'categories', 'source', 'submitted_by',
                  'start_date', 'start_time', 'hidden', 'duplicate_of']:
        if field in item:
            val = item[field]
            event[field] = float(val) if isinstance(val, Decimal) else val
    return event


def get_all_events(date_prefix=None):
    """Query DcTechEvents materialized table for active events, optionally filtered by YYYY-MM prefix."""
    from datetime import date as _date
    table = _get_materialized_table()
    items = []

    if date_prefix:
        year, month = date_prefix.split('-')
        start = f"{year}-{month}-01"
        next_month = int(month) + 1
        if next_month > 12:
            end = f"{int(year) + 1}-01-01"
        else:
            end = f"{year}-{next_month:02d}-01"
        kce = Key('status').eq('ACTIVE') & Key('date').between(start, end)
    else:
        today = _date.today().isoformat()
        kce = Key('status').eq('ACTIVE') & Key('date').gte(today)

    query_kwargs = {'IndexName': 'DateIndex', 'KeyConditionExpression': kce}
    response = table.query(**query_kwargs)
    items.extend(response.get('Items', []))
    while 'LastEvaluatedKey' in response:
        response = table.query(**query_kwargs, ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))

    return sorted(
        [_materialized_event_to_dict(item) for item in items],
        key=lambda x: (str(x.get('date', '') or ''), str(x.get('time', '') or '')),
    )


def _materialized_event_to_dict(item):
    """Convert a DcTechEvents item to a dict suitable for templates."""
    event = {}
    for field in ['eventId', 'title', 'date', 'time', 'end_date', 'url',
                  'location', 'cost', 'source', 'group', 'categories',
                  'city', 'state', 'hidden', 'duplicate_of']:
        if field in item:
            val = item[field]
            event[field] = float(val) if isinstance(val, Decimal) else val
    # Alias eventId → guid for template consistency
    event['guid'] = event.get('eventId', '')
    return event


def get_materialized_event(guid):
    """Get a single event from the DcTechEvents table by eventId."""
    table = _get_materialized_table()
    response = table.get_item(Key={'eventId': guid})
    item = response.get('Item')
    return _materialized_event_to_dict(item) if item else None


def get_event_from_config(guid):
    """Get an EVENT#{guid} entity from the config table, or None if not found."""
    table = _get_table()
    response = table.get_item(Key={'PK': f'EVENT#{guid}', 'SK': 'META'})
    item = response.get('Item')
    return _event_item_to_dict(item) if item else None


def update_event(guid, data):
    """Update an EVENT#{guid} entity in the config table with the given fields."""
    table = _get_table()
    date = data.get('date', '')
    time_val = data.get('time', '00:00')

    update_parts = ['GSI1PK = :gsi1pk', 'GSI1SK = :gsi1sk']
    expr_values = {
        ':gsi1pk': f'DATE#{date}',
        ':gsi1sk': f'TIME#{time_val}',
    }
    expr_names = {}

    updatable_fields = ['title', 'url', 'date', 'time', 'end_date', 'cost',
                        'city', 'state', 'all_day', 'categories', 'location',
                        'hidden', 'duplicate_of']
    for field in updatable_fields:
        if field in data and data[field] is not None:
            safe_key = f'#f_{field}'
            expr_names[safe_key] = field
            update_parts.append(f'{safe_key} = :{field}')
            expr_values[f':{field}'] = data[field]

    update_expr = 'SET ' + ', '.join(update_parts)
    kwargs = {
        'Key': {'PK': f'EVENT#{guid}', 'SK': 'META'},
        'UpdateExpression': update_expr,
        'ExpressionAttributeValues': expr_values,
    }
    if expr_names:
        kwargs['ExpressionAttributeNames'] = expr_names
    table.update_item(**kwargs)


def promote_draft_to_event(draft):
    """Promote an approved event draft to an EVENT entity in the config table."""
    table = _get_table()
    now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    guid = draft['id']
    date = draft.get('date', '')

    item = {
        'PK': f'EVENT#{guid}',
        'SK': 'META',
        'GSI1PK': f'DATE#{date}',
        'GSI1SK': f'TIME#{draft.get("time", "00:00")}',
        'source': 'submitted',
        'submitted_by': draft.get('submitter_email', ''),
        'created_at': now,
    }

    for field in ['title', 'url', 'date', 'time', 'end_date', 'cost',
                  'city', 'state', 'all_day', 'categories']:
        if draft.get(field) is not None:
            item[field] = draft[field]

    table.put_item(Item=item)
    return guid


# ─── OVERRIDE operations ──────────────────────────────────────────

def get_all_overrides():
    """Get all event overrides."""
    table = _get_table()
    items = []

    response = table.scan(
        FilterExpression=Attr('PK').begins_with('OVERRIDE#') & Attr('SK').eq('META'),
    )
    items.extend(response.get('Items', []))
    while 'LastEvaluatedKey' in response:
        response = table.scan(
            FilterExpression=Attr('PK').begins_with('OVERRIDE#') & Attr('SK').eq('META'),
            ExclusiveStartKey=response['LastEvaluatedKey'],
        )
        items.extend(response.get('Items', []))

    return [_override_item_to_dict(item) for item in items]


def get_override(guid):
    """Get a single override by GUID."""
    table = _get_table()
    response = table.get_item(Key={'PK': f'OVERRIDE#{guid}', 'SK': 'META'})
    item = response.get('Item')
    return _override_item_to_dict(item) if item else None


def put_override(guid, data):
    """Create or update an OVERRIDE entity."""
    table = _get_table()
    item = {
        'PK': f'OVERRIDE#{guid}',
        'SK': 'META',
        **{k: v for k, v in data.items() if v is not None},
    }
    table.put_item(Item=item)


def delete_override(guid):
    """Delete an override by GUID."""
    table = _get_table()
    table.delete_item(Key={'PK': f'OVERRIDE#{guid}', 'SK': 'META'})


def bulk_delete_events(guids, actor_email):
    """Hide multiple events by creating overrides or deleting manual records."""
    for guid in guids:
        manual = get_event_from_config(guid)
        if manual:
            # For manual events, we just set hidden=True in the record
            update_event(guid, {'hidden': True})
        else:
            # For iCal events, create/update override
            override = get_override(guid) or {}
            override['hidden'] = True
            override['edited_by'] = actor_email
            put_override(guid, override)


def bulk_set_category(guids, category_slug, actor_email):
    """Add a category to multiple events."""
    for guid in guids:
        manual = get_event_from_config(guid)
        if manual:
            cats = manual.get('categories', [])
            if category_slug not in cats:
                cats.append(category_slug)
                update_event(guid, {'categories': cats})
        else:
            override = get_override(guid) or {}
            # We might need the materialized event to see existing categories
            mat = get_materialized_event(guid) or {}
            cats = override.get('categories')
            if cats is None:
                cats = mat.get('categories', [])
            
            if category_slug not in cats:
                cats.append(category_slug)
                override['categories'] = cats
                override['edited_by'] = actor_email
                put_override(guid, override)


def bulk_combine_events(guids, target_guid, actor_email):
    """Mark multiple events as duplicates of a target event."""
    if target_guid in guids:
        guids = [g for g in guids if g != target_guid]
    
    for guid in guids:
        manual = get_event_from_config(guid)
        if manual:
            update_event(guid, {'duplicate_of': target_guid})
        else:
            override = get_override(guid) or {}
            override['duplicate_of'] = target_guid
            override['edited_by'] = actor_email
            put_override(guid, override)


def _override_item_to_dict(item):
    """Convert a DynamoDB OVERRIDE item to a dict."""
    guid = item['PK'].split('#', 1)[1]
    override = {'guid': guid}
    for field in ['categories', 'edited_by', 'title', 'url',
                  'location', 'time', 'hidden', 'duplicate_of']:
        if field in item:
            override[field] = item[field]
    return override


# ─── CATEGORY operations ──────────────────────────────────────────

def get_all_categories():
    """Get all categories."""
    table = _get_table()
    items = []

    response = table.scan(
        FilterExpression=Attr('PK').begins_with('CATEGORY#') & Attr('SK').eq('META'),
    )
    items.extend(response.get('Items', []))
    while 'LastEvaluatedKey' in response:
        response = table.scan(
            FilterExpression=Attr('PK').begins_with('CATEGORY#') & Attr('SK').eq('META'),
            ExclusiveStartKey=response['LastEvaluatedKey'],
        )
        items.extend(response.get('Items', []))

    categories = {}
    for item in items:
        slug = item['PK'].split('#', 1)[1]
        categories[slug] = {
            'slug': slug,
            'name': item.get('name', ''),
            'description': item.get('description', ''),
        }
    return categories
