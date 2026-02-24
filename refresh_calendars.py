#!/usr/bin/env python3
import os
import yaml
import icalendar
import requests
import json
import pytz
import hashlib
from datetime import datetime, timedelta, timezone, date
import re
from pathlib import Path
import sys
import extruct
from w3lib.html import get_base_url
from location_utils import extract_location_info
from urllib.parse import urlparse
import recurring_ical_events
import dynamo_data

# Load configuration
CONFIG_FILE = 'config.yaml'
config = {}
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r') as f:
        config = yaml.safe_load(f)

# Initialize timezone from config
timezone_name = config.get('timezone', 'US/Eastern')
local_tz = pytz.timezone(timezone_name)

# User agent for HTTP requests
USER_AGENT = 'dctech.events/1.0 (+https://dctech.events)'

# Constants - data paths
DATA_DIR = '_data'
CACHE_DIR = '_cache'  # Shared cache directory
ICAL_CACHE_DIR = os.path.join(CACHE_DIR, 'ical')
REFRESH_FLAG_FILE = os.path.join(DATA_DIR, '.refreshed')

# Ensure directories exist
os.makedirs(ICAL_CACHE_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

def should_fetch(meta_data, group_id):
    """
    Check if we should fetch new data based on last fetch time
    """
    last_fetch = meta_data.get('last_fetch')
    if last_fetch:
        last_fetch_time = datetime.fromisoformat(last_fetch)
        time_since_fetch = datetime.now(timezone.utc) - last_fetch_time
        if time_since_fetch < timedelta(hours=4):
            print(f"Data for {group_id} was fetched less than 4 hours ago, using cached version")
            return False
    return True


def is_safe_url(url):
    """
    Check if a URL is safe to render in an href.
    Only allows http:// and https:// schemes.
    """
    if not url:
        return True
    url = str(url).strip().lower()
    return url.startswith('http://') or url.startswith('https://')


def fetch_ical_and_extract_events(url, group_id, group=None):
    """
    Fetch an iCal file, visit each event link to extract JSON-LD event data, and cache it locally.
    """
    try:
        print(f"Fetching iCal feed from {url}")
        cache_file = os.path.join(ICAL_CACHE_DIR, f"{group_id}.json")
        cache_meta_file = os.path.join(ICAL_CACHE_DIR, f"{group_id}.meta")

        existing_events = []
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    existing_events = json.load(f)
            except Exception:
                pass

        headers = {'User-Agent': USER_AGENT}
        meta_data = {}

        if os.path.exists(cache_meta_file):
            with open(cache_meta_file, 'r') as f:
                meta_data = json.load(f)
                if not should_fetch(meta_data, group_id):
                    if os.path.exists(cache_file):
                        with open(cache_file, 'r') as f:
                            return json.load(f)
                    return None

                if 'etag' in meta_data:
                    headers['If-None-Match'] = meta_data['etag']
                if 'last_modified' in meta_data:
                    headers['If-Modified-Since'] = meta_data['last_modified']

        response = requests.get(url, headers=headers)

        if response.status_code == 304:
            print(f"iCal feed for {group_id} not modified, using cached version")
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    return json.load(f)
            return None

        if response.status_code != 200:
            print(f"Error fetching iCal from {url}: HTTP {response.status_code}")
            return None

        calendar = icalendar.Calendar.from_ical(response.text)
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname or ''
        is_luma_feed = (hostname == 'api.lu.ma' or 
                       hostname == 'api2.luma.com' or 
                       (hostname == 'luma.com' and '/ics' in parsed_url.path))

        start_date = datetime.now(timezone.utc)
        end_date = start_date + timedelta(days=60)
        event_instances = recurring_ical_events.of(calendar).between(start_date, end_date)

        events = []
        for component in event_instances:
            try:
                event_url = str(component.get('url', '')) if component.get('url') else None
                using_fallback = False

                if is_luma_feed and not event_url:
                    event_location = str(component.get('location', ''))
                    if event_location and ('http://' in event_location or 'https://' in event_location):
                        url_match = re.search(r'https?://[^\s]+', event_location)
                        if url_match:
                            event_url = url_match.group(0)

                if not event_url:
                    event_description = str(component.get('description', ''))
                    url_match = re.search(r'https?://(?:lu\.ma|luma\.com)/[^\s\\]+', event_description)
                    if url_match:
                        event_url = url_match.group(0)

                if not event_url and group and group.get('fallback_url'):
                    event_url = group.get('fallback_url')
                    using_fallback = True

                if not event_url:
                    continue

                scan_for_metadata = group.get('scan_for_metadata', True) if group else True
                event_data = None
                if not using_fallback and scan_for_metadata:
                    try:
                        event_response = requests.get(event_url, headers={'User-Agent': USER_AGENT}, timeout=10)
                        event_response.raise_for_status()
                        base_url = get_base_url(event_response.text, event_response.url)
                        data = extruct.extract(event_response.text, base_url=base_url, syntaxes=['json-ld'])
                        for item in data.get('json-ld', []):
                            if item.get('@type') in ['Event', 'BusinessEvent']:
                                event_data = item
                                break
                    except Exception:
                        pass

                if event_data:
                    final_url = group.get('url_override') if group and group.get('url_override') else event_url
                    if not is_safe_url(final_url):
                        final_url = ''

                    event = {
                        'title': event_data.get('name', str(component.get('summary', ''))),
                        'description': event_data.get('description', str(component.get('description', ''))),
                        'url': final_url,
                    }

                    location = event_data.get('location', {})
                    if isinstance(location, list):
                        for loc in location:
                            if isinstance(loc, dict) and loc.get('@type') == 'Place':
                                location = loc
                                break
                        else:
                            event['location_type'] = 'virtual'
                            location = None

                    if isinstance(location, dict) and location.get('@type') == 'VirtualLocation':
                        event['location_type'] = 'virtual'
                        location = None

                    if isinstance(location, dict):
                        address = location.get('address', {})
                        if isinstance(address, dict):
                            locality = address.get('addressLocality', '')
                            region = address.get('addressRegion', '')
                            if locality and region:
                                state_map = {
                                    'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR',
                                    'CALIFORNIA': 'CA', 'COLORADO': 'CO', 'CONNECTICUT': 'CT', 'DELAWARE': 'DE',
                                    'FLORIDA': 'FL', 'GEORGIA': 'GA', 'HAWAII': 'HI', 'IDAHO': 'ID',
                                    'ILLINOIS': 'IL', 'INDIANA': 'IN', 'IOWA': 'IA', 'KANSAS': 'KS',
                                    'KENTUCKY': 'KY', 'LOUISIANA': 'LA', 'MAINE': 'ME', 'MARYLAND': 'MD',
                                    'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI', 'MINNESOTA': 'MN', 'MISSISSIPPI': 'MS',
                                    'MISSOURI': 'MO', 'MONTANA': 'MT', 'NEBRASKA': 'NE', 'NEVADA': 'NV',
                                    'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ', 'NEW MEXICO': 'NM', 'NEW YORK': 'NY',
                                    'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND', 'OHIO': 'OH', 'OKLAHOMA': 'OK',
                                    'OREGON': 'OR', 'PENNSYLVANIA': 'PA', 'RHODE ISLAND': 'RI', 'SOUTH CAROLINA': 'SC',
                                    'SOUTH DAKOTA': 'SD', 'TENNESSEE': 'TN', 'TEXAS': 'TX', 'UTAH': 'UT',
                                    'VERMONT': 'VT', 'VIRGINIA': 'VA', 'WASHINGTON': 'WA', 'WEST VIRGINIA': 'WV',
                                    'WISCONSIN': 'WI', 'WYOMING': 'WY', 'DISTRICT OF COLUMBIA': 'DC'
                                }
                                state = region.upper()
                                if state in state_map: state = state_map[state]
                                city = 'Washington' if state == 'DC' else locality
                                event['location'] = f"{city}, {state}"
                            else:
                                event['location'] = ''
                        else:
                            city, state = extract_location_info(str(address))
                            event['location'] = f"{city}, {state}" if city and state else str(address)
                    else:
                        city, state = extract_location_info(str(location))
                        event['location'] = f"{city}, {state}" if city and state else str(location)

                    start_date = event_data.get('startDate')
                    if start_date:
                        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                        local_start = start_dt.astimezone(local_tz)
                        event['start_date'] = local_start.strftime('%Y-%m-%d')
                        event['start_time'] = local_start.strftime('%H:%M')
                        event['date'] = event['start_date']
                        event['time'] = event['start_time']

                    end_date = event_data.get('endDate')
                    if end_date:
                        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                        local_end = end_dt.astimezone(local_tz)
                        event['end_date'] = local_end.strftime('%Y-%m-%d')
                        event['end_time'] = local_end.strftime('%H:%M')
                    elif start_date:
                        event['end_date'] = event['start_date']
                        event['end_time'] = event['start_time']

                else:
                    start = component.get('dtstart').dt
                    end = component.get('dtend').dt if component.get('dtend') else start
                    if isinstance(start, datetime) and start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)
                    if isinstance(end, datetime) and end.tzinfo is None:
                        end = end.replace(tzinfo=timezone.utc)
                    localstart = start.astimezone(local_tz)
                    localend = end.astimezone(local_tz)
                    event_location = str(component.get('location', ''))
                    if event_location and ('http://' in event_location or 'https://' in event_location):
                        event_location = ''
                    city, state = extract_location_info(event_location)
                    if city and state:
                        event_location = f"{city}, {state}"
                    final_url = group.get('url_override') if group and group.get('url_override') else event_url
                    if not is_safe_url(final_url):
                        final_url = ''

                    event = {
                        'title': str(component.get('summary', '')),
                        'description': str(component.get('description', '')),
                        'location': event_location,
                        'start_date': localstart.strftime('%Y-%m-%d'),
                        'start_time': localstart.strftime('%H:%M'),
                        'end_date': localend.strftime('%Y-%m-%d'),
                        'end_time': localend.strftime('%H:%M'),
                        'url': final_url,
                        'date': localstart.strftime('%Y-%m-%d'),
                        'time': localstart.strftime('%H:%M'),
                    }
                events.append(event)
            except Exception as e:
                print(f'Error processing event: {str(e)}')
                continue

        today_str = datetime.now(local_tz).strftime('%Y-%m-%d')
        remembered_events = [e for e in existing_events if e.get('start_date') == today_str]
        if remembered_events:
            events_map = {}
            for e in remembered_events:
                key = (e.get('url'), e.get('title'), e.get('start_date'), e.get('start_time'))
                events_map[key] = e
            for e in events:
                key = (e.get('url'), e.get('title'), e.get('start_date'), e.get('start_time'))
                events_map[key] = e
            events = list(events_map.values())
            
        events.sort(key=lambda x: (str(x.get('date', '')), str(x.get('time', ''))))
        with open(cache_file, 'w') as f:
            json.dump(events, f)

        new_meta = {}
        if 'ETag' in response.headers: new_meta['etag'] = response.headers['ETag']
        if 'Last-Modified' in response.headers: new_meta['last_modified'] = response.headers['Last-Modified']
        new_meta['last_fetch'] = datetime.now(timezone.utc).isoformat()
        with open(cache_meta_file, 'w') as f:
            json.dump(new_meta, f)

        return events
    except Exception as e:
        print(f"Error fetching iCal feed from {url}: {str(e)}")
        return None

def calculate_event_hash(date_str, time_str, title, url=None):
    """Calculate MD5 hash for event identification (matches generate_month_data.py)."""
    uid_parts = [date_str, time_str, title]
    if url:
        uid_parts.append(url)
    uid_base = '-'.join(str(p) for p in uid_parts)
    return hashlib.md5(uid_base.encode('utf-8')).hexdigest()


def write_events_to_dynamo(events, group):
    """
    Write fetched iCal events directly to the config table as EVENT entities.

    Handles:
    - Preserving overridden fields (tracked in 'overrides' map on EVENT entity)
    - Preserving createdAt on existing events
    - Category resolution (event → group → empty)
    - Setting all GSI keys for consolidated queries
    """
    categories = dynamo_data.get_all_categories()
    group_name = str(group.get('name', ''))
    group_website = str(group.get('website', ''))
    group_categories = group.get('categories', [])
    suppress_urls = group.get('suppress_urls', [])
    suppress_guids = group.get('suppress_guid', [])

    # Get allowed states from config
    allowed_states = config.get('only_states', [])

    written = 0
    for event in events:
        guid = calculate_event_hash(
            event.get('date', ''),
            event.get('time', ''),
            event.get('title', ''),
            event.get('url'),
        )

        # Apply suppressions
        if event.get('url') in suppress_urls:
            continue
        if guid in suppress_guids:
            continue

        # Apply state filter
        if allowed_states:
            location = event.get('location', '')
            if location:
                city, state = extract_location_info(location)
                if state and state not in allowed_states:
                    continue

        # Resolve categories: event-level → group-level → empty
        event_cats = event.get('categories', [])
        if not event_cats and group_categories:
            event_cats = [c for c in group_categories if c in categories]

        data = {
            'title': event.get('title', ''),
            'date': event.get('date', ''),
            'time': event.get('time', ''),
            'url': event.get('url', ''),
            'location': event.get('location', ''),
            'description': event.get('description', ''),
            'group': group_name,
            'group_website': group_website,
            'source': 'ical',
        }

        # Optional fields
        for field in ['start_date', 'start_time', 'end_date', 'end_time',
                      'location_type', 'city', 'state', 'cost']:
            if event.get(field):
                data[field] = event[field]

        if event_cats:
            data['categories'] = event_cats

        dynamo_data.put_ical_event(guid, data)
        written += 1

    print(f"  Wrote {written} events from {group.get('id', '?')} to config table")
    return written


def handle_disappeared_events(current_guids, group_id):
    """
    Handle events that disappeared from the iCal feed.

    Same-day stability: events whose date is today are NEVER removed (source
    feeds like meetup.com drop past events mid-day). Events that disappear
    on a future date get soft-deleted (status='REMOVED').
    """
    from boto3.dynamodb.conditions import Key, Attr
    table = dynamo_data._get_table()
    today_str = datetime.now(pytz.timezone(timezone_name)).strftime('%Y-%m-%d')

    # Find existing iCal events for this group
    response = table.scan(
        FilterExpression=(
            Attr('PK').begins_with('EVENT#') &
            Attr('SK').eq('META') &
            Attr('source').eq('ical') &
            Attr('group').eq(group_id)
        ),
        ProjectionExpression='PK, #d, #s',
        ExpressionAttributeNames={'#d': 'date', '#s': 'status'},
    )
    existing = response.get('Items', [])
    while 'LastEvaluatedKey' in response:
        response = table.scan(
            FilterExpression=(
                Attr('PK').begins_with('EVENT#') &
                Attr('SK').eq('META') &
                Attr('source').eq('ical') &
                Attr('group').eq(group_id)
            ),
            ProjectionExpression='PK, #d, #s',
            ExpressionAttributeNames={'#d': 'date', '#s': 'status'},
            ExclusiveStartKey=response['LastEvaluatedKey'],
        )
        existing.extend(response.get('Items', []))

    removed = 0
    for item in existing:
        guid = item['PK'].split('#', 1)[1]
        if guid in current_guids:
            continue
        if item.get('status') == 'REMOVED':
            continue

        event_date = str(item.get('date', ''))

        # Same-day stability: keep today's events
        if event_date == today_str:
            continue

        # Past events that disappeared: soft-delete
        # Future events that disappeared: also soft-delete (genuine cancellations)
        table.update_item(
            Key={'PK': f'EVENT#{guid}', 'SK': 'META'},
            UpdateExpression='SET #s = :removed REMOVE GSI4PK, GSI4SK',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={':removed': 'REMOVED'},
        )
        removed += 1

    if removed:
        print(f"  Soft-deleted {removed} disappeared events from {group_id}")


def refresh_calendars(write_to_dynamo=True):
    """
    Fetch all iCal files from groups stored in DynamoDB.

    Args:
        write_to_dynamo: If True, write events directly to config table.
            If False, only cache to JSON files (legacy behavior).
    """
    print("Refreshing calendars from DynamoDB...")
    groups = dynamo_data.get_active_groups()
    updated = False

    for group in groups:
        if 'ical' in group and group['ical']:
            events = fetch_ical_and_extract_events(group['ical'], group['id'], group)
            if events is not None:
                updated = True

                if write_to_dynamo:
                    written = write_events_to_dynamo(events, group)

                    # Track which GUIDs we just wrote for this group
                    current_guids = set()
                    for event in events:
                        guid = calculate_event_hash(
                            event.get('date', ''),
                            event.get('time', ''),
                            event.get('title', ''),
                            event.get('url'),
                        )
                        current_guids.add(guid)

                    # Handle events that disappeared from feed
                    group_name = str(group.get('name', ''))
                    handle_disappeared_events(current_guids, group_name)

    if updated:
        with open(REFRESH_FLAG_FILE, 'w') as f:
            f.write(datetime.now().isoformat())
        print("Calendars refreshed successfully")
    else:
        print("No calendar updates needed")

    return updated

def main():
    os.makedirs(ICAL_CACHE_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    refresh_calendars()
    return 0

if __name__ == "__main__":
    sys.exit(main())
