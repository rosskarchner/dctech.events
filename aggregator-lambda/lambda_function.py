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
import csv
import uuid
import html
import unicodedata
import re
import chardet

from boto3.dynamodb.conditions import Key


# Initialize S3 and DynamoDB clients with conditional endpoint URLs
s3_endpoint_url = os.environ.get('AWS_S3_ENDPOINT_URL')
s3_args = {}
if s3_endpoint_url:
    s3_args['endpoint_url'] = s3_endpoint_url

s3 = boto3.resource('s3', **s3_args)

dynamodb_endpoint_url = os.environ.get('AWS_ENDPOINT_URL')
dynamodb_args = {}
if dynamodb_endpoint_url:
    dynamodb_args['endpoint_url'] = dynamodb_endpoint_url

dynamodb = boto3.resource('dynamodb', **dynamodb_args)
cache_bucket_name = os.environ.get('CACHE_BUCKET')
if cache_bucket_name:
    cache_bucket = s3.Bucket(cache_bucket_name)
groups_table = dynamodb.Table(os.environ['GROUPS_TABLE'])
events_table = dynamodb.Table(os.environ['EVENTS_TABLE'])
local_timezone = pytz.timezone(os.environ['TIMEZONE'])


def fetch_ical(url, group_id):
    try:
        print(f"Fetching calendar from {url}")
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
        if cache_bucket_name:
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

def sanitize_text(text):
    """
    Ensure text is properly encoded as UTF-8 using chardet for encoding detection.
    Handles HTML entities and special characters.
    
    Args:
        text: The text to sanitize
        
    Returns:
        Sanitized text as UTF-8 string
    """
    if text is None:
        return ""
    
    # Convert to string if not already
    if not isinstance(text, str):
        text = str(text)
    
    try:
        # First, detect the encoding if the text is not ASCII
        if any(ord(c) > 127 for c in text):
            # Convert to bytes for chardet
            byte_str = text.encode('utf-8', errors='replace')
            detected = chardet.detect(byte_str)
            encoding = detected['encoding'] or 'utf-8'
            
            # Decode with detected encoding and re-encode as UTF-8
            if encoding.lower() != 'utf-8':
                text = byte_str.decode(encoding, errors='replace')
        
        # Unescape HTML entities
        text = html.unescape(text)
        
        # Handle any remaining HTML character references
        text = re.sub(r'&(#x[0-9a-f]+|#[0-9]+);', 
                     lambda m: chr(int(m.group(1)[2:], 16)) if m.group(1).startswith('#x') 
                              else chr(int(m.group(1)[1:])), 
                     text)
        
        # Handle specific problematic characters
        replacements = {
            'â': "'",  # â often appears instead of a smart quote
            '\u2018': "'",  # Left single quote
            '\u2019': "'",  # Right single quote
            '\u201c': '"',  # Left double quote
            '\u201d': '"',  # Right double quote
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Simple normalization to handle quotes and special characters
        text = unicodedata.normalize('NFC', text)
        
        return text
    except Exception as e:
        print(f"Error sanitizing text: {str(e)}")
        # If any error occurs, return the original text
        return text

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

    # Get SITEURL from environment or use default
    site_url = os.environ.get('SITEURL', 'http://localhost:5000')
    # Remove trailing slash if present
    if site_url.endswith('/'):
        site_url = site_url[:-1]
    # Create a site slug for the partition key prefix
    site_slug = site_url.replace('http://', '').replace('https://', '').replace(':', '_').replace('/', '_')

    # Create unique ID for event
    monthslug = localstart.strftime("%Y-%m")
    eventslug = localstart.strftime("%d-%H:%M")
    partition_key = f"{site_slug}#EventsForMonth{monthslug}"
    sort_key = f"{eventslug}{group['id']}:{event.get('uid', '')}"

    # Extract group information
    group_id = group['id']
    group_name = sanitize_text(group.get('name', 'Unknown Group'))
    group_website = sanitize_text(group.get('website', ''))
    
    # Get event URL or use fallback URL if provided
    event_url = sanitize_text(event.get('url', ''))
    if not event_url and group.get('fallback_url'):
        event_url = sanitize_text(group.get('fallback_url'))
        
    # If there's still no URL, return None to skip this event
    if not event_url:
        return None

    # Get event summary and sanitize
    event_summary = sanitize_text(event.get('summary', ''))
    event_description = sanitize_text(event.get('description', ''))
    event_location = sanitize_text(event.get('location', ''))

    return {
        'month': partition_key,
        'sort': sort_key,
        'sourceId': group_id,  # Keep sourceId for backward compatibility
        'groupId': group_id,   # Add groupId as the new field name
        'groupName': group_name,  # Add group name
        'groupWebsite': group_website,  # Add group website
        'id': hashlib.sha256(sort_key.encode()).hexdigest(),
        'title': event_summary,
        'description': event_description,
        'location': event_location,
        'startDate': start.isoformat(),
        'endDate': end.isoformat(),
        'localstartDate': localstart.isoformat(),
        'localendDate': localend.isoformat(),
        'url': event_url,
        'status': f"{site_slug}!APPROVED",  # Namespace the status with site slug
        'lastUpdated': datetime.now(timezone.utc).isoformat(),
        'date': localstart.strftime('%Y-%m-%d')  # Add date field for GSI
    }

def load_sample_groups():
    """
    Load sample groups from the CSV file into the DynamoDB table
    """
    try:
        print("Loading sample groups from CSV file...")
        
        # First, clear all existing items from the table
        try:
            # Get all items from the table
            scan_response = groups_table.scan()
            items = scan_response.get('Items', [])
            
            # If there are items, delete them in batches
            if items:
                print(f"Found {len(items)} existing items to delete")
                
                # Delete items in batches of 25 (DynamoDB batch limit)
                with groups_table.batch_writer() as batch:
                    for item in items:
                        batch.delete_item(Key={'id': item['id']})
                
                print(f"Deleted all existing items from {os.environ['GROUPS_TABLE']} table")
            else:
                print(f"No existing items found in {os.environ['GROUPS_TABLE']} table")
                
        except Exception as e:
            print(f"Error clearing table: {str(e)}")
        
        # Always use localhost as the domain for sample groups
        site_slug = "localhost_5000"
        
        # Track groups we've already processed to avoid duplicates
        processed_names = set()
        groups_loaded = 0
        
        # Open the CSV file
        with open('sample-groups.csv', 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            
            # Process each row in the CSV
            for row in reader:
                # Skip if we've already processed this group name
                if row['name'] in processed_names:
                    print(f"Skipping duplicate group: {row['name']}")
                    continue
                
                # Add to processed set
                processed_names.add(row['name'])
                
                # Generate a unique ID for the group with site prefix
                group_id = f"{site_slug}!{str(uuid.uuid4())}"
                
                # Create the group item with sanitized text
                group_item = {
                    'id': group_id,
                    'name': sanitize_text(row['name']),
                    'website': sanitize_text(row['website']),
                    'ical': sanitize_text(row['ical']),
                    'approval_status': f"{site_slug}!APPROVED",  # Set status to APPROVED as requested
                    'active': True,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'organization_name': sanitize_text(row['name'])  # Using name as organization_name for GSI
                }
                
                # Add fallback_url if it exists
                if row['fallback_url']:
                    group_item['fallback_url'] = sanitize_text(row['fallback_url'])
                
                # Put the item in the DynamoDB table
                groups_table.put_item(Item=group_item)
                groups_loaded += 1
                
        print(f"Successfully loaded {groups_loaded} groups from sample-groups.csv")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Sample groups loaded successfully',
                'count': groups_loaded
            })
        }
    except Exception as e:
        print(f"Error loading sample groups: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def handler(event, context):
    # Check if this is a request to load sample groups
    if isinstance(event, dict) and event.get('action') == 'load-samples':
        return load_sample_groups()
    
    try:
        # Get SITEURL from environment or use default
        site_url = os.environ.get('SITEURL', 'http://localhost:5000')
        # Remove trailing slash if present
        if site_url.endswith('/'):
            site_url = site_url[:-1]
        # Create a site slug for filtering by ID prefix
        site_slug = site_url.replace('http://', '').replace('https://', '').replace(':', '_').replace('/', '_')
        
        # Query groups table for approved groups with the site prefix
        response = groups_table.scan(
            FilterExpression="(approval_status = :status OR approval_status = :namespaced_status) AND begins_with(id, :site_prefix)",
            ExpressionAttributeValues={
                ":status": "APPROVED",
                ":namespaced_status": f"{site_slug}!APPROVED",
                ":site_prefix": f"{site_slug}!"
            }
        )
        groups = response.get('Items', [])
        
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
                            
                        key_tuple = (item['month'], item['sort'])
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
                    key_tuple = (event['month'], event['sort'])
                    if key_tuple not in processed_keys:
                        processed_keys.add(key_tuple)
                        transaction_items.append({
                            'Delete': {
                                'TableName': events_table.name,
                                'Key': {
                                    'month': event['month'],
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
