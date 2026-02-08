import boto3
import os
import yaml
from datetime import datetime
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal

# Load configuration
CONFIG_FILE = 'config.yaml'
config = {}
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r') as f:
        config = yaml.safe_load(f)

TABLE_NAME = config.get('dynamodb_table', 'DcTechEvents')

def convert_floats(obj):
    """
    Recursively convert floats to Decimals for DynamoDB.
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: convert_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_floats(v) for v in obj]
    return obj

def get_table():
    dynamodb = boto3.resource('dynamodb')
    return dynamodb.Table(TABLE_NAME)

def get_future_events():
    """
    Get all active events with date >= today.
    """
    table = get_table()
    today = datetime.now().strftime('%Y-%m-%d')
    
    try:
        response = table.query(
            IndexName='DateIndex',
            KeyConditionExpression=Key('status').eq('ACTIVE') & Key('date').gte(today)
        )
        events = response.get('Items', [])
        
        while 'LastEvaluatedKey' in response:
            response = table.query(
                IndexName='DateIndex',
                KeyConditionExpression=Key('status').eq('ACTIVE') & Key('date').gte(today),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            events.extend(response.get('Items', []))
            
        return events
    except ClientError as e:
        print(f"Error fetching events from DynamoDB: {e}")
        return []

def get_all_active_events_map():
    """
    Get map of all active events (eventId -> item) to check existence/createdAt.
    """
    table = get_table()
    events_map = {}
    
    # Scan/Query DateIndex? 
    # Since we want to preserve createdAt for *any* event we are about to write, 
    # and we might be writing events further in future, querying DateIndex with date >= today covers most.
    # But what if we are updating an old event? (Unlikely for "upcoming").
    # A Scan on the main table might be safer if the dataset is small, but Query DateIndex is better practice.
    # We'll stick to Query DateIndex >= today, assuming we don't care about past events.
    
    events = get_future_events()
    for event in events:
        events_map[event['eventId']] = event
        
    return events_map

def sync_events(new_events):
    """
    Sync list of new events to DynamoDB.
    - Inserts new events.
    - Updates existing events (preserving createdAt).
    - Deletes events in DB that are not in new_events (and are >= today).
    """
    table = get_table()
    existing_events_map = get_all_active_events_map()
    
    # Prepare batch operations
    # Note: boto3 batch_writer handles buffering, but doesn't do "Delete if not present" automatically.
    
    # 1. Update/Insert
    with table.batch_writer() as batch:
        for event in new_events:
            event_id = event['guid']
            
            # Prepare Item
            item = event.copy()
            item['eventId'] = event_id
            item['status'] = 'ACTIVE'
            
            # Preserve createdAt or set new
            if event_id in existing_events_map:
                if 'createdAt' in existing_events_map[event_id]:
                    item['createdAt'] = existing_events_map[event_id]['createdAt']
            else:
                item['createdAt'] = datetime.now().isoformat()
            
            # Handle float/decimal conversion if needed? 
            # YAML loader might produce standard types. DynamoDB handles most.
            
            # Convert any floats to Decimals
            item = convert_floats(item)
            
            batch.put_item(Item=item)
            
    # 2. Delete missing future events
    # Identify IDs in existing_events_map that are NOT in new_events
    # Note: existing_events_map already only contains events where date >= today
    new_event_ids = set(e['guid'] for e in new_events)
    
    for event_id, event in existing_events_map.items():
        if event_id not in new_event_ids:
            # This event was in the upcoming list but is now gone
            # (e.g. cancelled or removed from source)
            print(f"Deleting removed future event: {event.get('title', event_id)}")
            table.delete_item(Key={'eventId': event_id})

def get_recently_added(limit=50):
    """
    Get recently added events from CreatedIndex.
    """
    table = get_table()
    try:
        response = table.query(
            IndexName='CreatedIndex',
            KeyConditionExpression=Key('status').eq('ACTIVE'),
            ScanIndexForward=False, # Descending sort by createdAt
            Limit=limit
        )
        return response.get('Items', [])
    except ClientError as e:
        print(f"Error fetching recently added events: {e}")
        return []

