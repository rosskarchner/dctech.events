#!/usr/bin/env python3
import os
import yaml
import icalendar
import requests
import json
import pytz
from datetime import datetime, timedelta, timezone, date
import glob
import re
from pathlib import Path
import sys
import extruct
from w3lib.html import get_base_url
from address_utils import normalize_address
from urllib.parse import urlparse

# Load configuration
CONFIG_FILE = 'config.yaml'
config = {}
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r') as f:
        config = yaml.safe_load(f)

# Initialize timezone from config
timezone_name = config.get('timezone', 'US/Eastern')
local_tz = pytz.timezone(timezone_name)

# Constants - data paths
GROUPS_DIR = '_groups'
DATA_DIR = '_data'
CACHE_DIR = '_cache'  # Shared cache directory
ICAL_CACHE_DIR = os.path.join(CACHE_DIR, 'ical')
CURRENT_DAY_FILE = os.path.join(DATA_DIR, 'current_day.txt')
REFRESH_FLAG_FILE = os.path.join(DATA_DIR, '.refreshed')

# Ensure directories exist
os.makedirs(ICAL_CACHE_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

def should_fetch(meta_data, group_id):
    """
    Check if we should fetch new data based on last fetch time
    
    Args:
        meta_data: Dictionary containing metadata including last_fetch
        group_id: The ID of the group (for logging)
        
    Returns:
        bool: True if we should fetch, False otherwise
    """
    last_fetch = meta_data.get('last_fetch')
    if last_fetch:
        last_fetch_time = datetime.fromisoformat(last_fetch)
        time_since_fetch = datetime.now(timezone.utc) - last_fetch_time
        if time_since_fetch < timedelta(hours=4):
            print(f"Data for {group_id} was fetched less than 4 hours ago, using cached version")
            return False
    return True


def fetch_ical_and_extract_events(url, group_id, group=None):
    """
    Fetch an iCal file, visit each event link to extract JSON-LD event data, and cache it locally.

    Args:
        url: The URL of the iCal file
        group_id: The ID of the group (used for caching)
        group: The group dictionary (optional, for fallback_url support)

    Returns:
        A list of event dictionaries if changed, None otherwise
    """
    try:
        print(f"Fetching iCal feed from {url}")
        # Create cache files - store as JSON like RSS
        cache_file = os.path.join(ICAL_CACHE_DIR, f"{group_id}.json")
        cache_meta_file = os.path.join(ICAL_CACHE_DIR, f"{group_id}.meta")

        # Load existing events for 'memory' of today's events
        existing_events = []
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    existing_events = json.load(f)
            except Exception:
                pass

        # Prepare headers for conditional GET
        headers = {}
        meta_data = {}

        # Check if we have cached metadata
        if os.path.exists(cache_meta_file):
            with open(cache_meta_file, 'r') as f:
                meta_data = json.load(f)

                # Check if we should skip fetching due to time constraint
                if not should_fetch(meta_data, group_id):
                    if os.path.exists(cache_file):
                        with open(cache_file, 'r') as f:
                            return json.load(f)
                    return None

                # Add conditional GET headers
                if 'etag' in meta_data:
                    headers['If-None-Match'] = meta_data['etag']
                if 'last_modified' in meta_data:
                    headers['If-Modified-Since'] = meta_data['last_modified']

        # Make the request
        response = requests.get(url, headers=headers)

        # If the content hasn't changed (304 Not Modified)
        if response.status_code == 304:
            print(f"iCal feed for {group_id} not modified, using cached version")
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    return json.load(f)
            return None

        # If we got an error
        if response.status_code != 200:
            print(f"Error fetching iCal from {url}: HTTP {response.status_code}")
            return None

        # Parse the iCal feed
        calendar = icalendar.Calendar.from_ical(response.text)

        # Check if this is a lu.ma feed by parsing the URL hostname
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname or ''
        is_luma_feed = (hostname == 'api.lu.ma' or 
                       hostname == 'api2.luma.com' or 
                       (hostname == 'luma.com' and '/ics' in parsed_url.path))

        # Process each event and extract event data
        events = []
        for component in calendar.walk('VEVENT'):
            try:
                # Get the event URL from the iCal event
                event_url = str(component.get('url', '')) if component.get('url') else None
                using_fallback = False

                # Special handling for lu.ma feeds: check if location field contains a URL
                if is_luma_feed and not event_url:
                    event_location = str(component.get('location', ''))
                    # Check if location looks like a URL
                    if event_location and ('http://' in event_location or 'https://' in event_location):
                        # Extract the URL from the location field
                        # The location might be just a URL or might have other text
                        url_match = re.search(r'https?://[^\s]+', event_location)
                        if url_match:
                            event_url = url_match.group(0)
                            print(f"Using URL from location field for lu.ma event: {event_url}")

                # If no URL in event, try fallback_url from group
                if not event_url and group and group.get('fallback_url'):
                    event_url = group.get('fallback_url')
                    using_fallback = True

                # Skip if still no URL
                if not event_url:
                    print(f"Skipping event without URL: {component.get('summary', 'Unknown')}")
                    continue

                # Check if group wants to scan for metadata (default: True)
                scan_for_metadata = group.get('scan_for_metadata', True) if group else True

                # Only try JSON-LD extraction if we have an event-specific URL and scanning is enabled
                event_data = None
                if not using_fallback and scan_for_metadata:
                    # Fetch the event page
                    event_response = requests.get(event_url)
                    event_response.raise_for_status()

                    # Extract JSON-LD data
                    base_url = get_base_url(event_response.text, event_response.url)
                    data = extruct.extract(event_response.text, base_url=base_url, syntaxes=['json-ld'])

                    # Find Event schema
                    for item in data.get('json-ld', []):
                        if item.get('@type') == 'Event':
                            event_data = item
                            break

                # Create event from JSON-LD if available, otherwise from iCal data
                if event_data:
                    # Check if group has a URL override
                    final_url = group.get('url_override') if group and group.get('url_override') else event_url
                    
                    # Convert to our event format from JSON-LD
                    event = {
                        'title': event_data.get('name', str(component.get('summary', ''))),
                        'description': event_data.get('description', str(component.get('description', ''))),
                        'url': final_url,
                    }

                    # Handle location with both place name and address
                    location = event_data.get('location', {})
                    physical_location = None

                    # Handle array of locations (hybrid events)
                    if isinstance(location, list):
                        # Find the physical location (Place type) in the array
                        for loc in location:
                            if isinstance(loc, dict) and loc.get('@type') == 'Place':
                                physical_location = loc
                                break
                        # If no physical location found, skip this event
                        if not physical_location:
                            print(f"Skipping virtual-only event: {component.get('summary', 'Unknown')}")
                            continue
                        location = physical_location

                    # Skip virtual-only events
                    if isinstance(location, dict) and location.get('@type') == 'VirtualLocation':
                        print(f"Skipping virtual-only event: {component.get('summary', 'Unknown')}")
                        continue

                    if isinstance(location, dict):
                        place_name = location.get('name', '')
                        address = location.get('address', {})

                        # Handle address object
                        if isinstance(address, dict):
                            street = address.get('streetAddress', '')
                            locality = address.get('addressLocality', '')
                            region = address.get('addressRegion', '')

                            # Build formatted address
                            address_parts = []
                            if street: address_parts.append(street)
                            if locality: address_parts.append(locality)
                            if region: address_parts.append(region)
                            formatted_address = ', '.join(address_parts)

                            if place_name and formatted_address:
                                event['location'] = normalize_address(f"{place_name}, {formatted_address}")
                            elif place_name:
                                event['location'] = normalize_address(place_name)
                            elif formatted_address:
                                event['location'] = normalize_address(formatted_address)
                        else:
                            # Handle string address
                            if place_name and address:
                                event['location'] = normalize_address(f"{place_name}, {address}")
                            elif place_name:
                                event['location'] = normalize_address(place_name)
                            elif address:
                                event['location'] = normalize_address(address)
                    else:
                        event['location'] = normalize_address(str(location)) if location else ''

                    # Handle submitter information if present
                    submitter = event_data.get('submitter', {})
                    if isinstance(submitter, dict):
                        name = submitter.get('name', '')
                        if name and name.lower() != 'anonymous':
                            event['submitter_name'] = name
                            if submitter.get('url'):
                                event['submitter_link'] = submitter['url']

                    # Parse start date/time from JSON-LD
                    start_date = event_data.get('startDate')
                    if start_date:
                        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                        local_start = start_dt.astimezone(local_tz)
                        event['start_date'] = local_start.strftime('%Y-%m-%d')
                        event['start_time'] = local_start.strftime('%H:%M')
                        event['date'] = event['start_date']  # For sorting
                        event['time'] = event['start_time']  # For sorting

                    # Parse end date/time from JSON-LD
                    end_date = event_data.get('endDate')
                    if end_date:
                        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                        local_end = end_dt.astimezone(local_tz)
                        event['end_date'] = local_end.strftime('%Y-%m-%d')
                        event['end_time'] = local_end.strftime('%H:%M')
                    elif start_date:  # If no end date, use start date
                        event['end_date'] = event['start_date']
                        event['end_time'] = event['start_time']

                else:
                    # Fallback: create event from iCal data if JSON-LD not available
                    start = component.get('dtstart').dt
                    end = component.get('dtend').dt if component.get('dtend') else start

                    # Convert to UTC if datetime is naive
                    if isinstance(start, datetime) and start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)
                    if isinstance(end, datetime) and end.tzinfo is None:
                        end = end.replace(tzinfo=timezone.utc)

                    # Convert to local timezone
                    localstart = start.astimezone(local_tz)
                    localend = end.astimezone(local_tz)

                    event_location = str(component.get('location', ''))

                    # Check if group has a URL override
                    final_url = group.get('url_override') if group and group.get('url_override') else event_url

                    event = {
                        'title': str(component.get('summary', '')),
                        'description': str(component.get('description', '')),
                        'location': normalize_address(event_location),
                        'start_date': localstart.strftime('%Y-%m-%d'),
                        'start_time': localstart.strftime('%H:%M'),
                        'end_date': localend.strftime('%Y-%m-%d'),
                        'end_time': localend.strftime('%H:%M'),
                        'url': final_url,
                        'date': localstart.strftime('%Y-%m-%d'),  # For sorting
                        'time': localstart.strftime('%H:%M'),     # For sorting
                    }

                events.append(event)

            except Exception as e:
                print(f'Error processing event {component.get("summary", "Unknown")}: {str(e)}')
                continue

        # Give the calendar 'memory' for today's events that might have dropped off the feed
        today_str = datetime.now(local_tz).strftime('%Y-%m-%d')
        remembered_events = [e for e in existing_events if e.get('start_date') == today_str]
        
        if remembered_events:
            # Deduplicate: use a map to prefer newer data for the same event
            # Key is (url, title, start_date, start_time)
            events_map = {}
            for e in remembered_events:
                key = (e.get('url'), e.get('title'), e.get('start_date'), e.get('start_time'))
                events_map[key] = e
            for e in events:
                key = (e.get('url'), e.get('title'), e.get('start_date'), e.get('start_time'))
                events_map[key] = e
            events = list(events_map.values())
            
        # Sort events by date and time
        events.sort(key=lambda x: (str(x.get('date', '')), str(x.get('time', ''))))

        # Save the events
        with open(cache_file, 'w') as f:
            json.dump(events, f)

        # Save the metadata
        new_meta = {}
        if 'ETag' in response.headers:
            new_meta['etag'] = response.headers['ETag']
        if 'Last-Modified' in response.headers:
            new_meta['last_modified'] = response.headers['Last-Modified']
        new_meta['last_fetch'] = datetime.now(timezone.utc).isoformat()

        with open(cache_meta_file, 'w') as f:
            json.dump(new_meta, f)

        return events

    except Exception as e:
        print(f"Error fetching iCal feed from {url}: {str(e)}")
        return None


def load_groups():
    """
    Load all groups from the _groups directory
    
    Returns:
        A list of group dictionaries
    """
    groups = []
    for file_path in glob.glob(os.path.join(GROUPS_DIR, '*.yaml')):
        try:
            with open(file_path, 'r') as f:
                group = yaml.safe_load(f)
                # Add the group ID (filename without extension)
                group['id'] = os.path.splitext(os.path.basename(file_path))[0]
                groups.append(group)
        except Exception as e:
            print(f"Error loading group from {file_path}: {str(e)}")
    
    return groups

def is_current_day_file_updated():
    """
    Check if the current day file exists and is up to date.
    
    Returns:
        bool: True if the file is up to date, False otherwise
    """
    today = datetime.now(local_tz).date()
    today_str = today.strftime('%Y-%m-%d')
    
    # Check if the file exists
    if not os.path.exists(CURRENT_DAY_FILE):
        return False
    
    # Read the file content
    with open(CURRENT_DAY_FILE, 'r') as f:
        content = f.read().strip()
    
    # Check if the content matches today's date
    return content == today_str

def update_current_day_file():
    """
    Update the current day file with today's date.
    """
    today = datetime.now(local_tz).date()
    today_str = today.strftime('%Y-%m-%d')
    
    # Write today's date to the file
    with open(CURRENT_DAY_FILE, 'w') as f:
        f.write(today_str)
    
    return True

def refresh_calendars():
    """
    Fetch all iCal files and RSS feeds from groups
    
    Returns:
        True if any calendars were updated, False otherwise
    """
    print("Refreshing calendars...")
    groups = load_groups()
    updated = False
    
    # Check if the current day file is up to date
    if not is_current_day_file_updated():
        print("Current day file is out of date, forcing update...")
        update_current_day_file()
        updated = True
    
    for group in groups:
        if not group.get('active', True):
            continue

        # Check if group has ical field (iCal with JSON-LD augmentation)
        if 'ical' in group and group['ical']:
            events = fetch_ical_and_extract_events(group['ical'], group['id'], group)
            if events is not None:
                updated = True
    
    # Create a flag file to indicate that calendars were refreshed
    if updated:
        with open(REFRESH_FLAG_FILE, 'w') as f:
            f.write(datetime.now().isoformat())
        print("Calendars refreshed successfully")
    else:
        print("No calendar updates needed")
    
    return updated

def main():
    """
    Main function to run the calendar refresh
    """
    # Create cache directory if it doesn't exist
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(ICAL_CACHE_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    # Always check and update the current day file
    day_file_updated = False
    if not is_current_day_file_updated():
        print("Current day file is out of date, updating...")
        update_current_day_file()
        day_file_updated = True

    # Run the refresh
    updated = refresh_calendars()

    # Always return success (0) - 'no updates needed' is a successful state
    # Only errors (exceptions) should cause non-zero exit codes
    return 0

if __name__ == "__main__":
    sys.exit(main())