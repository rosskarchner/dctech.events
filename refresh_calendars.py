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
import feedparser
import extruct
from w3lib.html import get_base_url
from address_utils import normalize_address

# Load configuration
CONFIG_FILE = 'config.yaml'
config = {}
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r') as f:
        config = yaml.safe_load(f)

# Initialize timezone from config or use default
timezone_name = config.get('timezone', 'US/Eastern')
local_tz = pytz.timezone(timezone_name)

# Constants
GROUPS_DIR = '_groups'
DATA_DIR = '_data'
CACHE_DIR = '_cache'
ICAL_CACHE_DIR = os.path.join(CACHE_DIR, 'ical')
RSS_CACHE_DIR = os.path.join(CACHE_DIR, 'rss')
CURRENT_DAY_FILE = os.path.join(DATA_DIR, 'current_day.txt')
REFRESH_FLAG_FILE = os.path.join(DATA_DIR, '.refreshed')

# Ensure directories exist
os.makedirs(ICAL_CACHE_DIR, exist_ok=True)
os.makedirs(RSS_CACHE_DIR, exist_ok=True)
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

def fetch_ical(url, group_id):
    """
    Fetch an iCal file and cache it locally.
    Only update if:
    - Content has changed (using ETag or Last-Modified)
    - Last fetch was more than 4 hours ago

    Args:
        url: The URL of the iCal file
        group_id: The ID of the group (used for caching)

    Returns:
        The parsed iCal calendar if changed, None otherwise
    """
    try:
        print(f"Fetching calendar from {url}")
        # Create a cache key based on the group_id
        cache_file = os.path.join(ICAL_CACHE_DIR, f"{group_id}.ics")
        cache_meta_file = os.path.join(ICAL_CACHE_DIR, f"{group_id}.meta")

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
                            return icalendar.Calendar.from_ical(f.read())
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
            print(f"Calendar for {group_id} not modified, using cached version")
            with open(cache_file, 'r') as f:
                return icalendar.Calendar.from_ical(f.read())

        # If we got a successful response
        if response.status_code == 200:
            # Save the content
            with open(cache_file, 'w') as f:
                f.write(response.text)

            # Save the metadata
            new_meta = {}
            if 'ETag' in response.headers:
                new_meta['etag'] = response.headers['ETag']
            if 'Last-Modified' in response.headers:
                new_meta['last_modified'] = response.headers['Last-Modified']
            new_meta['last_fetch'] = datetime.now(timezone.utc).isoformat()

            with open(cache_meta_file, 'w') as f:
                json.dump(new_meta, f)

            # Parse and return the calendar
            return icalendar.Calendar.from_ical(response.text)

        # If we got an error
        print(f"Error fetching calendar from {url}: HTTP {response.status_code}")
        return None

    except Exception as e:
        print(f"Error fetching calendar from {url}: {str(e)}")
        return None

def fetch_ical_and_extract_events(url, group_id):
    """
    Fetch an iCal feed, visit each event link to extract JSON-LD event data, and cache it locally.
    Similar to fetch_rss_and_extract_events but for iCal feeds.

    Args:
        url: The URL of the iCal feed
        group_id: The ID of the group (used for caching)

    Returns:
        A list of event dictionaries if changed, None otherwise
    """
    try:
        print(f"Fetching iCal feed from {url}")
        # Create cache files - store enriched events as JSON
        cache_file = os.path.join(ICAL_CACHE_DIR, f"{group_id}.json")
        cache_meta_file = os.path.join(ICAL_CACHE_DIR, f"{group_id}.meta")

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

        # Fetch the iCal feed
        response = requests.get(url, headers=headers)

        # If the content hasn't changed (304 Not Modified)
        if response.status_code == 304:
            print(f"iCal feed for {group_id} not modified, using cached version")
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    return json.load(f)
            return None

        # If we got a successful response
        if response.status_code != 200:
            print(f"Error fetching iCal from {url}: HTTP {response.status_code}")
            return None

        # Parse the iCal calendar
        calendar = icalendar.Calendar.from_ical(response.text)

        # Process each event and extract JSON-LD data
        events = []
        for component in calendar.walk('VEVENT'):
            try:
                # Get the event URL
                event_url = component.get('url')
                if not event_url:
                    # Skip events without URLs - we can't fetch JSON-LD without a URL
                    continue

                event_url = str(event_url)

                # Get basic event info from iCal
                start = component.get('dtstart').dt
                end = component.get('dtend').dt if component.get('dtend') else start

                # Convert to UTC if datetime is naive
                if isinstance(start, datetime) and start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                if isinstance(end, datetime) and end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)

                # Convert to local timezone
                local_start = start.astimezone(local_tz)
                local_end = end.astimezone(local_tz)

                # Fetch the event page
                try:
                    event_response = requests.get(event_url, timeout=10)
                    event_response.raise_for_status()
                except Exception as e:
                    print(f"Error fetching event page {event_url}: {str(e)}")
                    # Fall back to basic iCal data if we can't fetch the page
                    event = {
                        'title': str(component.get('summary', '')),
                        'description': str(component.get('description', '')),
                        'location': str(component.get('location', '')),
                        'url': event_url,
                        'start_date': local_start.strftime('%Y-%m-%d'),
                        'start_time': local_start.strftime('%H:%M'),
                        'end_date': local_end.strftime('%Y-%m-%d'),
                        'end_time': local_end.strftime('%H:%M'),
                        'date': local_start.strftime('%Y-%m-%d'),
                        'time': local_start.strftime('%H:%M'),
                    }
                    events.append(event)
                    continue

                # Extract JSON-LD data
                base_url = get_base_url(event_response.text, event_response.url)
                data = extruct.extract(event_response.text, base_url=base_url, syntaxes=['json-ld'])

                # Find Event schema
                event_data = None
                for item in data.get('json-ld', []):
                    if item.get('@type') == 'Event':
                        event_data = item
                        break

                if event_data:
                    # Use JSON-LD data (similar to RSS processing)
                    event = {
                        'title': event_data.get('name', str(component.get('summary', ''))),
                        'description': event_data.get('description', str(component.get('description', ''))),
                        'url': event_url,
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
                            print(f"Skipping virtual-only event: {event.get('title', 'Unknown')}")
                            continue
                        location = physical_location

                    # Skip virtual-only events
                    if isinstance(location, dict) and location.get('@type') == 'VirtualLocation':
                        print(f"Skipping virtual-only event: {event.get('title', 'Unknown')}")
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
                        event['date'] = event['start_date']
                        event['time'] = event['start_time']
                    else:
                        # Fall back to iCal dates
                        event['start_date'] = local_start.strftime('%Y-%m-%d')
                        event['start_time'] = local_start.strftime('%H:%M')
                        event['date'] = event['start_date']
                        event['time'] = event['start_time']

                    # Parse end date/time from JSON-LD
                    end_date = event_data.get('endDate')
                    if end_date:
                        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                        local_end = end_dt.astimezone(local_tz)
                        event['end_date'] = local_end.strftime('%Y-%m-%d')
                        event['end_time'] = local_end.strftime('%H:%M')
                    else:
                        # Fall back to iCal dates
                        event['end_date'] = local_end.strftime('%Y-%m-%d')
                        event['end_time'] = local_end.strftime('%H:%M')

                    events.append(event)
                else:
                    # No JSON-LD found, fall back to basic iCal data
                    print(f"No JSON-LD found for {event_url}, using iCal data")
                    event = {
                        'title': str(component.get('summary', '')),
                        'description': str(component.get('description', '')),
                        'location': normalize_address(str(component.get('location', ''))),
                        'url': event_url,
                        'start_date': local_start.strftime('%Y-%m-%d'),
                        'start_time': local_start.strftime('%H:%M'),
                        'end_date': local_end.strftime('%Y-%m-%d'),
                        'end_time': local_end.strftime('%H:%M'),
                        'date': local_start.strftime('%Y-%m-%d'),
                        'time': local_start.strftime('%H:%M'),
                    }
                    events.append(event)

            except Exception as e:
                print(f"Error processing iCal event: {str(e)}")
                continue

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

def fetch_rss_and_extract_events(url, group_id):
    """
    Fetch an RSS feed, visit each event link to extract JSON-LD event data, and cache it locally.
    
    Args:
        url: The URL of the RSS feed
        group_id: The ID of the group (used for caching)
        
    Returns:
        A list of event dictionaries if changed, None otherwise
    """
    try:
        print(f"Fetching RSS feed from {url}")
        # Create cache files
        cache_file = os.path.join(RSS_CACHE_DIR, f"{group_id}.json")
        cache_meta_file = os.path.join(RSS_CACHE_DIR, f"{group_id}.meta")
        
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
        
        # Parse the RSS feed
        feed = feedparser.parse(url, request_headers=headers)
        
        # If the content hasn't changed (304 Not Modified)
        if hasattr(feed, 'status') and feed.status == 304:
            print(f"RSS feed for {group_id} not modified, using cached version")
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    return json.load(f)
            return None
        
        # Process each entry and extract event data
        events = []
        for entry in feed.entries:
            try:
                # Get the event page URL
                event_url = entry.link
                
                # Fetch the event page
                response = requests.get(event_url)
                response.raise_for_status()
                
                # Extract JSON-LD data
                base_url = get_base_url(response.text, response.url)
                data = extruct.extract(response.text, base_url=base_url, syntaxes=['json-ld'])
                
                # Find Event schema
                event_data = None
                for item in data.get('json-ld', []):
                    if item.get('@type') == 'Event':
                        event_data = item
                        break
                
                if event_data:
                    # Convert to our event format
                    event = {
                        'title': event_data.get('name', entry.title),
                        'description': event_data.get('description', entry.get('description', '')),
                        'url': event_url,
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
                            print(f"Skipping virtual-only event: {event.get('title', 'Unknown')}")
                            continue
                        location = physical_location
                    
                    # Skip virtual-only events
                    if isinstance(location, dict) and location.get('@type') == 'VirtualLocation':
                        print(f"Skipping virtual-only event: {event.get('title', 'Unknown')}")
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
                    
                    # Parse start date/time
                    start_date = event_data.get('startDate')
                    if start_date:
                        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                        local_start = start_dt.astimezone(local_tz)
                        event['start_date'] = local_start.strftime('%Y-%m-%d')
                        event['start_time'] = local_start.strftime('%H:%M')
                        event['date'] = event['start_date']  # For sorting
                        event['time'] = event['start_time']  # For sorting
                    
                    # Parse end date/time
                    end_date = event_data.get('endDate')
                    if end_date:
                        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                        local_end = end_dt.astimezone(local_tz)
                        event['end_date'] = local_end.strftime('%Y-%m-%d')
                        event['end_time'] = local_end.strftime('%H:%M')
                    elif start_date:  # If no end date, use start date
                        event['end_date'] = event['start_date']
                        event['end_time'] = event['start_time']
                    
                    events.append(event)
            
            except Exception as e:
                print(f"Error processing event {entry.link}: {str(e)}")
                continue
        
        # Save the events
        with open(cache_file, 'w') as f:
            json.dump(events, f)
        
        # Save the metadata
        new_meta = {}
        if hasattr(feed, 'etag'):
            new_meta['etag'] = feed.etag
        if hasattr(feed, 'modified'):
            new_meta['last_modified'] = feed.modified
        new_meta['last_fetch'] = datetime.now(timezone.utc).isoformat()
        
        with open(cache_meta_file, 'w') as f:
            json.dump(new_meta, f)
        
        return events
        
    except Exception as e:
        print(f"Error fetching RSS feed from {url}: {str(e)}")
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

        if 'ical' in group and group['ical']:
            # Check if group wants JSON-LD extraction for iCal
            if group.get('ical_extract_jsonld', False):
                events = fetch_ical_and_extract_events(group['ical'], group['id'])
                if events is not None:
                    updated = True
            else:
                calendar = fetch_ical(group['ical'], group['id'])
                if calendar is not None:
                    updated = True
        elif 'rss' in group and group['rss']:
            events = fetch_rss_and_extract_events(group['rss'], group['id'])
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
    if not is_current_day_file_updated():
        print("Current day file is out of date, updating...")
        update_current_day_file()
    
    # Run the refresh
    updated = refresh_calendars()
    
    # Return exit code based on whether calendars were updated
    return 0 if updated else 1

if __name__ == "__main__":
    sys.exit(main())