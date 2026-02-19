#!/usr/bin/env python3
import os
import yaml
import icalendar
import requests
import json
import pytz
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

def refresh_calendars():
    """
    Fetch all iCal files from groups stored in DynamoDB
    """
    print("Refreshing calendars from DynamoDB...")
    groups = dynamo_data.get_active_groups()
    updated = False
    
    for group in groups:
        if 'ical' in group and group['ical']:
            events = fetch_ical_and_extract_events(group['ical'], group['id'], group)
            if events is not None:
                updated = True
    
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
