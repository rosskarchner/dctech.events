#!/usr/bin/env python3
import os
import yaml
import icalendar
import requests
import hashlib
import json
import pytz
from datetime import datetime, timedelta, timezone, date
import glob
import re
from pathlib import Path
import sys
import calendar as cal_module

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
SINGLE_EVENTS_DIR = '_single_events'
DATA_DIR = '_data'
CACHE_DIR = '_cache'
ICAL_CACHE_DIR = os.path.join(CACHE_DIR, 'ical')
CURRENT_DAY_FILE = os.path.join(DATA_DIR, 'current_day.txt')

# Ensure directories exist
os.makedirs(ICAL_CACHE_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Custom YAML representer for icalendar.prop.vText objects
def represent_vtext(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', str(data))

# Custom YAML representer for icalendar.prop.vUri objects
def represent_vuri(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', str(data))

# Register the custom representers with PyYAML
yaml.add_representer(icalendar.prop.vText, represent_vtext)
yaml.add_representer(icalendar.prop.vUri, represent_vuri)

def sanitize_text(text):
    """
    Sanitize text for safe usage
    """
    if text is None:
        return ""
    
    # Convert to string if not already
    if not isinstance(text, str):
        text = str(text)
    
    return text

def fetch_ical(url, group_id):
    """
    Fetch an iCal file and cache it locally.
    Only update if the content has changed (using ETag or Last-Modified).
    
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
            
            with open(cache_meta_file, 'w') as f:
                json.dump(new_meta, f)
            
            # Parse and return the calendar
            return icalendar.Calendar.from_ical(response.text)
        
        # If we got an error
        print(f"Error fetching calendar: {response.status_code}")
        return None
        
    except Exception as e:
        print(f"Error fetching calendar from {url}: {str(e)}")
        return None

def event_to_dict(event, group=None):
    """
    Convert an iCal event to a dictionary
    
    Args:
        event: The iCal event
        group: The group the event belongs to (optional)
        
    Returns:
        A dictionary representing the event
    """
    try:
        start = event.get('dtstart').dt
        end = event.get('dtend').dt if event.get('dtend') else start
        
        # Convert to UTC if datetime is naive
        if isinstance(start, datetime) and start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if isinstance(end, datetime) and end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        # Convert to local timezone
        localstart = start.astimezone(local_tz)
        localend = end.astimezone(local_tz)
        
        # Get event details and ensure they are strings, not icalendar.prop.vText objects
        event_summary = sanitize_text(event.get('summary', ''))
        event_description = sanitize_text(event.get('description', ''))
        event_location = sanitize_text(event.get('location', ''))
        
        # Get event URL or use fallback URL if provided
        event_url = sanitize_text(event.get('url', ''))
        if not event_url and group and group.get('fallback_url'):
            event_url = sanitize_text(group.get('fallback_url'))
            
        # If there's still no URL, skip this event
        if not event_url:
            return None
        
        # Create the event dictionary
        event_dict = {
            'title': event_summary,
            'description': event_description,
            'location': event_location,
            'start_date': localstart.strftime('%Y-%m-%d'),
            'start_time': localstart.strftime('%H:%M'),
            'end_date': localend.strftime('%Y-%m-%d'),
            'end_time': localend.strftime('%H:%M'),
            'url': event_url,
            'date': localstart.strftime('%Y-%m-%d'),  # For sorting
            'time': localstart.strftime('%H:%M'),     # For sorting
        }
        
        # Add group information if provided
        if group:
            event_dict['group'] = str(group.get('name', ''))
            event_dict['group_website'] = str(group.get('website', ''))
        
        return event_dict
    
    except Exception as e:
        print(f"Error converting event to dictionary: {str(e)}")
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

def load_single_events():
    """
    Load all single events from the _single_events directory
    
    Returns:
        A list of event dictionaries
    """
    events = []
    for file_path in glob.glob(os.path.join(SINGLE_EVENTS_DIR, '*.yaml')):
        try:
            with open(file_path, 'r') as f:
                event = yaml.safe_load(f)
                # Add the event ID (filename without extension)
                event['id'] = os.path.splitext(os.path.basename(file_path))[0]
                
                # Ensure date and time are in the correct format
                if 'date' in event and 'time' in event:
                    # Convert date to string if it's a date object
                    if isinstance(event['date'], date):
                        event['date'] = event['date'].strftime('%Y-%m-%d')
                    
                    # Create a datetime object - assume it's in local timezone
                    event_datetime_str = f"{event['date']} {event['time']}"
                    naive_dt = datetime.strptime(event_datetime_str, '%Y-%m-%d %H:%M')
                    
                    # Localize the datetime to the configured timezone
                    event_datetime = local_tz.localize(naive_dt)
                    
                    # Add formatted fields
                    event['start_date'] = event_datetime.strftime('%Y-%m-%d')
                    event['start_time'] = event_datetime.strftime('%H:%M')
                    event['end_date'] = event.get('end_date', event['start_date'])
                    event['end_time'] = event.get('end_time', event['start_time'])
                
                events.append(event)
        except Exception as e:
            print(f"Error loading event from {file_path}: {str(e)}")
    
    return events

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
    
    # Create a flag file to indicate that YAML files need to be updated
    with open(os.path.join(DATA_DIR, '.updated'), 'w') as f:
        f.write(datetime.now().isoformat())
    
    return True

def phase1_fetch_icals():
    """
    Phase 1: Fetch all iCal files from groups
    
    Returns:
        True if any calendars were updated, False otherwise
    """
    print("Phase 1: Fetching iCal files...")
    groups = load_groups()
    updated = False
    
    # Check if the current day file is up to date
    if not is_current_day_file_updated():
        print("Current day file is out of date, forcing update...")
        update_current_day_file()
        updated = True
    
    for group in groups:
        if 'ical' in group and group['ical'] and group.get('active', True):
            calendar = fetch_ical(group['ical'], group['id'])
            if calendar is not None:
                updated = True
    
    return updated

def phase2_generate_yaml():
    """
    Phase 2: Generate YAML files from iCal and single events
    
    Returns:
        True if any YAML files were updated, False otherwise
    """
    print("Phase 2: Generating YAML files...")
    
    # Load all groups
    groups = load_groups()
    
    # Load all single events
    single_events = load_single_events()
    
    # Collect all events
    all_events = []
    
    # Process iCal events
    for group in groups:
        if not group.get('active', True):
            continue
            
        if 'ical' in group and group['ical']:
            cache_file = os.path.join(ICAL_CACHE_DIR, f"{group['id']}.ics")
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r') as f:
                        calendar = icalendar.Calendar.from_ical(f.read())
                        
                        for component in calendar.walk('VEVENT'):
                            event_dict = event_to_dict(component, group)
                            if event_dict:
                                all_events.append(event_dict)
                except Exception as e:
                    print(f"Error processing calendar for group {group['id']}: {str(e)}")
    
    # Add single events
    all_events.extend(single_events)
    
    # Sort events by date and time
    all_events.sort(key=lambda x: (str(x.get('date', '')), str(x.get('time', ''))))
    
    # Get current date
    today = datetime.now(local_tz).date()
    current_month = today.month
    current_year = today.year
    
    # Calculate next month
    if current_month == 12:
        next_month = 1
        next_year = current_year + 1
    else:
        next_month = current_month + 1
        next_year = current_year
    
    # Filter events for upcoming.yaml (remainder of current month + next month)
    upcoming_events = []
    for event in all_events:
        event_date = datetime.strptime(event['date'], '%Y-%m-%d').date()
        
        # Include if event is today or later and in current or next month
        if event_date >= today and (
            (event_date.year == current_year and event_date.month == current_month) or
            (event_date.year == next_year and event_date.month == next_month)
        ):
            upcoming_events.append(event)
    
    # Group events by month for per-month files
    events_by_month = {}
    for event in all_events:
        event_date = datetime.strptime(event['date'], '%Y-%m-%d').date()
        month_key = f"{event_date.year}-{event_date.month:02d}"
        
        if month_key not in events_by_month:
            events_by_month[month_key] = []
        
        events_by_month[month_key].append(event)
    
    # Write upcoming.yaml
    upcoming_file = os.path.join(DATA_DIR, 'upcoming.yaml')
    with open(upcoming_file, 'w') as f:
        yaml.dump(upcoming_events, f, sort_keys=False)
    
    # Write per-month files
    for month_key, month_events in events_by_month.items():
        year, month = month_key.split('-')
        month_name = cal_module.month_name[int(month)].lower()
        month_file = os.path.join(DATA_DIR, f"{year}_{month_name}.yaml")
        
        with open(month_file, 'w') as f:
            yaml.dump(month_events, f, sort_keys=False)
    
    return True

def main():
    """
    Main function to run the aggregator
    """
    # Create cache directory if it doesn't exist
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(ICAL_CACHE_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Always check and update the current day file
    if not is_current_day_file_updated():
        print("Current day file is out of date, updating...")
        update_current_day_file()
    
    # Run Phase 1
    updated = phase1_fetch_icals()
    
    # Run Phase 2 if Phase 1 updated any calendars or if --force is specified
    if updated or '--force' in sys.argv:
        phase2_generate_yaml()
        print("YAML files updated successfully")
        # Create a flag file to indicate that YAML files were updated
        with open(os.path.join(DATA_DIR, '.updated'), 'w') as f:
            f.write(datetime.now().isoformat())
        return 0
    else:
        print("No updates needed")
        return 0

if __name__ == "__main__":
    sys.exit(main())