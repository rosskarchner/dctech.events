"""
Event Collection Lambda Function
Fetches iCal feeds and stores events in DynamoDB with "last seen" logic
"""
import os
import json
import boto3
import yaml
import icalendar
import requests
import pytz
import hashlib
from datetime import datetime, timedelta, timezone, date
from typing import List, Dict, Any, Optional
from decimal import Decimal
import extruct
from w3lib.html import get_base_url
import recurring_ical_events


# Environment variables
DYNAMODB_TABLE_NAME = os.getenv('DYNAMODB_TABLE_NAME')
ASSETS_BUCKET = os.getenv('ASSETS_BUCKET')
AWS_REGION = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
TIMEZONE_NAME = os.getenv('TIMEZONE', 'US/Eastern')

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
s3 = boto3.client('s3', region_name=AWS_REGION)
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

# Timezone
local_tz = pytz.timezone(TIMEZONE_NAME)

# HTTP cache for iCal feeds (stored in DynamoDB or S3)
CACHE_TABLE_NAME = os.getenv('CACHE_TABLE_NAME', DYNAMODB_TABLE_NAME + '-Cache')


def lambda_handler(event, context):
    """
    Main Lambda handler - refresh all calendars

    Args:
        event: Lambda event (can contain specific group_id to refresh)
        context: Lambda context

    Returns:
        Response with statistics
    """
    print("Starting calendar refresh")

    # Get groups from S3
    groups = load_groups_from_s3()
    print(f"Loaded {len(groups)} groups")

    # Filter to active groups with iCal feeds
    active_groups = [
        g for g in groups
        if g.get('active', False) and g.get('ical')
    ]
    print(f"Found {active_groups} active groups with iCal feeds")

    # Process each group
    stats = {
        'groups_processed': 0,
        'events_created': 0,
        'events_updated': 0,
        'errors': []
    }

    for group in active_groups:
        try:
            group_stats = process_group(group)
            stats['groups_processed'] += 1
            stats['events_created'] += group_stats['created']
            stats['events_updated'] += group_stats['updated']

        except Exception as e:
            error_msg = f"Error processing group {group.get('id')}: {str(e)}"
            print(error_msg)
            stats['errors'].append(error_msg)

    print(f"Calendar refresh complete: {stats}")

    return {
        'statusCode': 200,
        'body': json.dumps(stats)
    }


def load_groups_from_s3() -> List[Dict[str, Any]]:
    """Load group definitions from S3"""
    groups = []

    try:
        # List all YAML files in groups/ prefix
        response = s3.list_objects_v2(
            Bucket=ASSETS_BUCKET,
            Prefix='groups/'
        )

        if 'Contents' not in response:
            return []

        # Load each group YAML file
        for obj in response['Contents']:
            key = obj['Key']

            if not key.endswith(('.yaml', '.yml')):
                continue

            try:
                obj_response = s3.get_object(
                    Bucket=ASSETS_BUCKET,
                    Key=key
                )

                yaml_content = obj_response['Body'].read().decode('utf-8')
                group = yaml.safe_load(yaml_content)

                if group:
                    # Extract group ID from filename
                    filename = key.split('/')[-1]
                    group_id = filename.replace('.yaml', '').replace('.yml', '')
                    group['id'] = group_id
                    groups.append(group)

            except Exception as e:
                print(f"Error loading group from {key}: {e}")
                continue

        return groups

    except Exception as e:
        print(f"Error listing groups from S3: {e}")
        return []


def process_group(group: Dict[str, Any]) -> Dict[str, int]:
    """
    Process a single group - fetch iCal and update DynamoDB

    Args:
        group: Group dictionary

    Returns:
        Statistics dictionary
    """
    group_id = group['id']
    ical_url = group['ical']

    print(f"Processing group: {group_id}")

    # Fetch iCal feed
    events = fetch_ical_events(ical_url, group)

    if not events:
        print(f"No events fetched for {group_id}")
        return {'created': 0, 'updated': 0}

    print(f"Fetched {len(events)} events for {group_id}")

    # Get existing events from DynamoDB for this group
    existing_events = get_existing_events_for_group(group_id)

    # Implement "last seen" logic
    stats = update_events_in_dynamodb(
        new_events=events,
        existing_events=existing_events,
        group=group
    )

    return stats


def fetch_ical_events(
    ical_url: str,
    group: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Fetch and parse iCal feed

    Args:
        ical_url: URL of iCal feed
        group: Group dictionary

    Returns:
        List of event dictionaries
    """
    try:
        # Check HTTP cache (optional - can implement with DynamoDB)
        # For now, just fetch directly
        response = requests.get(ical_url, timeout=30)
        response.raise_for_status()

        # Parse iCal
        cal = icalendar.Calendar.from_ical(response.content)

        # Get recurring events for next 60 days
        start_date = datetime.now(local_tz)
        end_date = start_date + timedelta(days=60)

        events = []

        # Use recurring-ical-events to expand recurring events
        for component in recurring_ical_events.of(cal).between(
            start_date,
            end_date
        ):
            if component.name != 'VEVENT':
                continue

            try:
                event = parse_ical_event(component, group)
                if event:
                    events.append(event)

            except Exception as e:
                print(f"Error parsing event {component.get('SUMMARY', 'Unknown')}: {e}")
                continue

        return events

    except Exception as e:
        print(f"Error fetching iCal from {ical_url}: {e}")
        return []


def parse_ical_event(
    component: icalendar.Event,
    group: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Parse iCal event component into event dictionary

    Args:
        component: iCalendar event component
        group: Group dictionary

    Returns:
        Event dictionary or None if invalid
    """
    # Extract basic fields
    title = str(component.get('SUMMARY', 'Untitled Event'))
    description = str(component.get('DESCRIPTION', ''))
    location = str(component.get('LOCATION', ''))
    url = str(component.get('URL', ''))

    # Handle missing URL with fallback
    if not url:
        url = group.get('fallback_url', group.get('website', ''))

    # Parse start/end datetime
    dtstart = component.get('DTSTART')
    dtend = component.get('DTEND')

    if not dtstart:
        return None

    # Convert to datetime
    start_dt = dtstart.dt
    if isinstance(start_dt, date) and not isinstance(start_dt, datetime):
        # All-day event
        start_dt = datetime.combine(start_dt, datetime.min.time())
        start_dt = local_tz.localize(start_dt)

    elif isinstance(start_dt, datetime):
        # Ensure timezone
        if start_dt.tzinfo is None:
            start_dt = local_tz.localize(start_dt)
        else:
            start_dt = start_dt.astimezone(local_tz)

    # End datetime
    if dtend:
        end_dt = dtend.dt
        if isinstance(end_dt, date) and not isinstance(end_dt, datetime):
            end_dt = datetime.combine(end_dt, datetime.min.time())
            end_dt = local_tz.localize(end_dt)
        elif isinstance(end_dt, datetime):
            if end_dt.tzinfo is None:
                end_dt = local_tz.localize(end_dt)
            else:
                end_dt = end_dt.astimezone(local_tz)
    else:
        # Default to 1 hour duration
        end_dt = start_dt + timedelta(hours=1)

    # Extract location info (city, state)
    city, state = extract_location_info(location)

    # Determine location type
    location_type = 'virtual' if is_virtual_location(location) else 'in_person'

    # Generate event ID (hash of unique fields)
    event_id = generate_event_id(url, title, start_dt)

    # Build event dictionary
    event = {
        'event_id': event_id,
        'start_datetime': start_dt.isoformat(),
        'end_datetime': end_dt.isoformat(),
        'title': title,
        'description': description,
        'url': url,
        'location': location,
        'location_type': location_type,
        'city': city or '',
        'state': state or 'ALL',  # Default to ALL for GSI
        'group_id': group['id'],
        'group_name': group.get('name', ''),
        'group_website': group.get('website', ''),
        'source_type': 'ical',
        'last_seen_date': datetime.now(timezone.utc).date().isoformat(),
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }

    # Set TTL (7 days after event end)
    ttl_date = end_dt + timedelta(days=7)
    event['ttl'] = int(ttl_date.timestamp())

    return event


def extract_location_info(location: str) -> tuple:
    """
    Extract city and state from location string

    Args:
        location: Location string

    Returns:
        Tuple of (city, state)
    """
    # Simple extraction - in production, use the full location_utils
    location_lower = location.lower()

    # Check for virtual
    if any(term in location_lower for term in ['virtual', 'online', 'zoom']):
        return ('Virtual', None)

    # Extract state
    state = None
    if ', dc' in location_lower or 'washington' in location_lower:
        state = 'DC'
    elif ', md' in location_lower or 'maryland' in location_lower:
        state = 'MD'
    elif ', va' in location_lower or 'virginia' in location_lower:
        state = 'VA'

    # Extract city (simplified)
    parts = location.split(',')
    city = parts[0].strip() if parts else ''

    return (city, state)


def is_virtual_location(location: str) -> bool:
    """Check if location indicates virtual event"""
    location_lower = location.lower()
    virtual_terms = ['virtual', 'online', 'zoom', 'webinar', 'remote', 'web']
    return any(term in location_lower for term in virtual_terms)


def generate_event_id(url: str, title: str, start_dt: datetime) -> str:
    """
    Generate unique event ID

    Args:
        url: Event URL
        title: Event title
        start_dt: Start datetime

    Returns:
        SHA256 hash as event ID
    """
    key_str = f"{url}{title}{start_dt.isoformat()}"
    return hashlib.sha256(key_str.encode('utf-8')).hexdigest()


def get_existing_events_for_group(group_id: str) -> List[Dict[str, Any]]:
    """
    Get existing events from DynamoDB for a group

    Args:
        group_id: Group identifier

    Returns:
        List of existing events
    """
    try:
        # Query DynamoDB using GroupIndex
        # Get events starting from 7 days ago (to catch recent ones)
        start_date = (datetime.now(local_tz) - timedelta(days=7)).date()

        response = table.query(
            IndexName='GroupIndex',
            KeyConditionExpression='group_id = :gid AND start_datetime >= :start',
            ExpressionAttributeValues={
                ':gid': group_id,
                ':start': start_date.isoformat()
            }
        )

        events = response.get('Items', [])

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = table.query(
                IndexName='GroupIndex',
                KeyConditionExpression='group_id = :gid AND start_datetime >= :start',
                ExpressionAttributeValues={
                    ':gid': group_id,
                    ':start': start_date.isoformat()
                },
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            events.extend(response.get('Items', []))

        return events

    except Exception as e:
        print(f"Error querying existing events for {group_id}: {e}")
        return []


def update_events_in_dynamodb(
    new_events: List[Dict[str, Any]],
    existing_events: List[Dict[str, Any]],
    group: Dict[str, Any]
) -> Dict[str, int]:
    """
    Update events in DynamoDB with "last seen" logic

    The "last seen" logic:
    1. New events from iCal feed → create/update with last_seen_date = today
    2. Existing events still in feed → update last_seen_date = today
    3. Existing events NOT in feed:
       - If start_date == today → keep (preserve today's events)
       - If last_seen_date >= yesterday → keep (grace period)
       - Otherwise → let TTL handle deletion

    Args:
        new_events: Events from iCal feed
        existing_events: Events currently in DynamoDB
        group: Group dictionary

    Returns:
        Statistics dictionary
    """
    stats = {'created': 0, 'updated': 0}

    # Create lookup map for new events
    new_events_map = {e['event_id']: e for e in new_events}

    # Create lookup map for existing events
    existing_events_map = {e['event_id']: e for e in existing_events}

    today = datetime.now(timezone.utc).date().isoformat()
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()

    # Process new events
    for event_id, event in new_events_map.items():
        if event_id in existing_events_map:
            # Event exists - update last_seen_date
            existing = existing_events_map[event_id]

            # Update only if data changed or to refresh last_seen
            table.update_item(
                Key={
                    'event_id': event['event_id'],
                    'start_datetime': event['start_datetime']
                },
                UpdateExpression='SET last_seen_date = :today, updated_at = :now, #ttl = :ttl',
                ExpressionAttributeNames={
                    '#ttl': 'ttl'
                },
                ExpressionAttributeValues={
                    ':today': today,
                    ':now': datetime.now(timezone.utc).isoformat(),
                    ':ttl': event['ttl']
                }
            )
            stats['updated'] += 1

        else:
            # New event - create
            table.put_item(Item=event)
            stats['created'] += 1

    # Implement "memory" for today's events
    # Check existing events that are NOT in new feed
    for event_id, existing in existing_events_map.items():
        if event_id not in new_events_map:
            # Event not in latest feed
            start_date = existing.get('start_datetime', '').split('T')[0]
            last_seen = existing.get('last_seen_date', '')

            # Preserve today's events (memory logic)
            if start_date == today:
                print(f"Preserving today's event (memory): {existing.get('title')}")
                # Update last_seen_date to keep it alive
                table.update_item(
                    Key={
                        'event_id': existing['event_id'],
                        'start_datetime': existing['start_datetime']
                    },
                    UpdateExpression='SET last_seen_date = :today, updated_at = :now',
                    ExpressionAttributeValues={
                        ':today': today,
                        ':now': datetime.now(timezone.utc).isoformat()
                    }
                )

            # Grace period - keep if seen recently
            elif last_seen >= yesterday:
                print(f"Grace period for event: {existing.get('title')}")
                # Don't update - let it age out if still missing

            # Otherwise, let TTL handle deletion (no action needed)

    return stats
