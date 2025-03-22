import os
import boto3
import icalendar
import requests
from datetime import datetime, timezone
import hashlib
import json
import pytz
from datetime import timedelta

from boto3.dynamodb.conditions import Key


s3 = boto3.resource('s3')

dynamodb = boto3.resource('dynamodb')
cache_bucket =s3.Bucket(os.environ['CACHE_BUCKET'])
sources_table = dynamodb.Table(os.environ['SOURCES_TABLE'])
events_table = dynamodb.Table(os.environ['EVENTS_TABLE'])
local_timezone = pytz.timezone(os.environ['TIMEZONE'])


def fetch_ical(url, source_id):
    try:
        # Create a cache key based on the source_id
        cache_key = f"ical_cache/{source_id}.ics"
        
        # Fetch current content
        response = requests.get(url)
        response.raise_for_status()
        current_content = response.text
        
        # Calculate hash of current content
        current_hash = hashlib.sha256(current_content.encode()).hexdigest()
        
        # Try to get existing cached file
        try:
            cached_object = cache_bucket.Object(cache_key).get()
            cached_content = cached_object['Body'].read().decode('utf-8')
            cached_hash = hashlib.sha256(cached_content.encode()).hexdigest()
            
            if current_hash == cached_hash:
                # Content hasn't changed, no need to parse
                return None
                
        except Exception:
            # No cache exists yet, that's okay
            pass
            
        # Content is different or new, cache it
        cache_bucket.Object(cache_key).put(
            Body=current_content.encode('utf-8'),
            ContentType='text/calendar',
            Metadata={'content_hash': current_hash}
        )
        
        # Parse and return the calendar since content has changed
        return icalendar.Calendar.from_ical(current_content)
        
    except Exception as e:
        print(f"Error fetching calendar from {url}: {str(e)}")
        return None

def event_to_item(event, source_id):
    start = event.get('dtstart').dt
    end = event.get('dtend').dt if event.get('dtend') else start
    
    # Convert to UTC if datetime is naive
    if isinstance(start, datetime) and start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if isinstance(end, datetime) and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    localstart = start.astimezone(local_timezone)
    localend = end.astimezone(local_timezone)

    # Create unique ID for event
    weekslug=localstart.strftime("%G-W%V")
    eventslug = localstart.strftime("%u-%H:%M")
    partition_key = f"EventsForWeek{weekslug}"
    sort_key = f"{eventslug}{source_id}:{event.get('uid', '')}"

    return {
        'week': partition_key,
        'sort': sort_key,
        'sourceId': source_id,
        'id': hashlib.sha256(sort_key.encode()).hexdigest(),
        'title': str(event.get('summary', '')),
        'description': str(event.get('description', '')),
        'location': str(event.get('location', '')),
        'startDate': start.isoformat(),
        'endDate': end.isoformat(),
        'localstartDate': localstart.isoformat(),
        'localendDate': localend.isoformat(),
        'url': str(event.get('url', '')),
        'status': 'APPROVED',  # Since these are from trusted sources
        'lastUpdated': datetime.now(timezone.utc).isoformat()
    }

def handler(event, context):
    try:
        # Scan sources table
        response = sources_table.scan()
        sources = response['Items']

        # Process each source
        for source in sources:
            if not source.get('active', True):
                continue


            calendar = fetch_ical(source['ical_url'], source['id'])
            if calendar is None:
                print(f"No changes for source {source['id']}, skipping")
                continue

            processed_keys = set()
            transaction_items = []





            # Process each event for putting
            for component in calendar.walk('VEVENT'):
                try:
                    item = event_to_item(component, source['id'])
                    key_tuple = (item['week'], item['sort'])
                    processed_keys.add(key_tuple)
                    transaction_items.append({
                        'Put': {
                            'TableName': events_table.name,
                            'Item': item
                        }
                    })
                except Exception as e:
                    print(f"Error processing event: {str(e)}")
                    continue

            events_to_delete = events_table.query(
                IndexName='source-index',
                KeyConditionExpression=Key('sourceId').eq(source['id'])
            )

            # Add delete operations to transaction
            for event in events_to_delete['Items']:
                key_tuple = (event['week'], event['sort'])
                if key_tuple not in processed_keys:
                    processed_keys.add(key_tuple)
                    transaction_items.append({
                        'Delete': {
                            'TableName': events_table.name,
                            'Key': {
                                'week': event['week'],
                                'sort': event['sort']
                            }
                        }
                    })



            # Execute the transaction if there are items to process
            if transaction_items:
                try:
                    dynamodb.meta.client.transact_write_items(
                        TransactItems=transaction_items
                    )
                except Exception as e:
                    print(f"Transaction failed: {str(e)}")
                    # Handle the error appropriately
                    return {
                        'statusCode': 200,
                        'body': json.dumps('Processing complete')
                    }

    except Exception as e:
        print(f"Error in aggregator: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
