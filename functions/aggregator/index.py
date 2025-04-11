import os
import boto3
import icalendar
import requests
from datetime import datetime, timezone
import hashlib
import json
import pytz
from datetime import timedelta
from urllib.parse import urlparse

from boto3.dynamodb.conditions import Key


s3 = boto3.resource('s3')

dynamodb = boto3.resource('dynamodb')
cache_bucket = s3.Bucket(os.environ['CACHE_BUCKET'])
groups_table = dynamodb.Table(os.environ['GROUPS_TABLE'])
events_table = dynamodb.Table(os.environ['EVENTS_TABLE'])
local_timezone = pytz.timezone(os.environ['TIMEZONE'])


def fetch_ical(url, group_id):
    try:
        # Create a cache key based on the group_id
        cache_key = f"ical_cache/{group_id}.ics"
        
        url_parts = urlparse(url)

        if url_parts.scheme not in ['http', 'https']:
            url = url_parts._replace(scheme='https').geturl()

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

def event_to_item(event, group):
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
    weekslug = localstart.strftime("%G-W%V")
    eventslug = localstart.strftime("%u-%H:%M")
    partition_key = f"EventsForWeek{weekslug}"
    sort_key = f"{eventslug}{group['id']}:{event.get('uid', '')}"

    # Extract group information
    group_id = group['id']
    group_name = group.get('name', 'Unknown Group')
    group_website = group.get('website', '')
    
    # Get event URL or use fallback URL if provided
    event_url = str(event.get('url', ''))
    if not event_url and group.get('fallback_url'):
        event_url = group.get('fallback_url')
        
    # If there's still no URL, return None to skip this event
    if not event_url:
        return None

    return {
        'week': partition_key,
        'sort': sort_key,
        'sourceId': group_id,  # Keep sourceId for backward compatibility
        'groupId': group_id,   # Add groupId as the new field name
        'groupName': group_name,  # Add group name
        'groupWebsite': group_website,  # Add group website
        'id': hashlib.sha256(sort_key.encode()).hexdigest(),
        'title': str(event.get('summary', '')),
        'description': str(event.get('description', '')),
        'location': str(event.get('location', '')),
        'startDate': start.isoformat(),
        'endDate': end.isoformat(),
        'localstartDate': localstart.isoformat(),
        'localendDate': localend.isoformat(),
        'url': event_url,
        'status': 'APPROVED',  # Since these are from trusted sources
        'lastUpdated': datetime.now(timezone.utc).isoformat()
    }

def handler(event, context):
    try:
        # Query groups table for approved groups
        response = groups_table.query(
            IndexName='approval-status-index',
            KeyConditionExpression=Key('approval_status').eq('approved')
        )
        groups = response['Items']
        
        print(f"Found {len(groups)} approved groups")
        processed_count = 0
        skipped_count = 0
        error_count = 0
        skipped_events_count = 0

        # Process each group
        for group in groups:
            try:
                # Skip if no iCal URL or group is not active
                if not group.get('ical'):
                    print(f"Group {group.get('id')} ({group.get('name', 'Unknown')}) has no iCal URL, skipping")
                    skipped_count += 1
                    continue
                    
                if not group.get('active', True):
                    print(f"Group {group.get('id')} ({group.get('name', 'Unknown')}) is not active, skipping")
                    skipped_count += 1
                    continue

                print(f"Processing group {group.get('id')} ({group.get('name', 'Unknown')})")
                calendar = fetch_ical(group['ical'], group['id'])
                if calendar is None:
                    print(f"No changes for group {group.get('id')} ({group.get('name', 'Unknown')}), skipping")
                    skipped_count += 1
                    continue

                processed_keys = set()
                transaction_items = []
                event_count = 0
                local_skipped_events = 0

                # Process each event for putting
                for component in calendar.walk('VEVENT'):
                    try:
                        item = event_to_item(component, group)
                        # Skip events without a URL when no fallback URL is provided
                        if item is None:
                            local_skipped_events += 1
                            continue
                            
                        key_tuple = (item['week'], item['sort'])
                        processed_keys.add(key_tuple)
                        transaction_items.append({
                            'Put': {
                                'TableName': events_table.name,
                                'Item': item
                            }
                        })
                        event_count += 1
                    except Exception as e:
                        print(f"Error processing event for group {group.get('id')}: {str(e)}")
                        continue

                if local_skipped_events > 0:
                    print(f"Skipped {local_skipped_events} events without URLs for group {group.get('id')} ({group.get('name', 'Unknown')})")
                    skipped_events_count += local_skipped_events

                # Find events to delete (events that are no longer in the feed)
                # Use group-index instead of source-index
                events_to_delete = events_table.query(
                    IndexName='group-index',
                    KeyConditionExpression=Key('sourceId').eq(group['id'])
                )
                
                delete_count = 0
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
                        delete_count += 1

                # Execute the transaction if there are items to process
                if transaction_items:
                    try:
                        # Process in batches of 25 (DynamoDB transaction limit)
                        batch_count = 0
                        for i in range(0, len(transaction_items), 25):
                            batch = transaction_items[i:i+25]
                            dynamodb.meta.client.transact_write_items(
                                TransactItems=batch
                            )
                            batch_count += 1
                        
                        print(f"Successfully processed group {group.get('id')} ({group.get('name', 'Unknown')}): {event_count} events added/updated, {delete_count} events deleted, {batch_count} batches")
                        processed_count += 1
                    except Exception as e:
                        print(f"Transaction failed for group {group.get('id')} ({group.get('name', 'Unknown')}): {str(e)}")
                        error_count += 1
                else:
                    print(f"No changes needed for group {group.get('id')} ({group.get('name', 'Unknown')})")
                    processed_count += 1
            except Exception as e:
                print(f"Error processing group {group.get('id', 'Unknown ID')} ({group.get('name', 'Unknown')}): {str(e)}")
                error_count += 1

        print(f"Aggregation complete: {processed_count} groups processed, {skipped_count} groups skipped, {error_count} groups with errors, {skipped_events_count} events skipped due to missing URLs")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Processing complete',
                'processed': processed_count,
                'skipped_groups': skipped_count,
                'skipped_events': skipped_events_count,
                'errors': error_count
            })
        }

    except Exception as e:
        print(f"Error in aggregator: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
