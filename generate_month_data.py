#!/usr/bin/env python3
import os
import yaml
import icalendar
import pytz
from datetime import datetime, timedelta, timezone, date
import glob
import re
from pathlib import Path
import sys
import calendar as cal_module
import dateparser
import json
from address_utils import normalize_address

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
SINGLE_EVENTS_DIR = '_single_events'
DATA_DIR = '_data'
CACHE_DIR = '_cache'  # Shared cache directory
ICAL_CACHE_DIR = os.path.join(CACHE_DIR, 'ical')
REFRESH_FLAG_FILE = os.path.join(DATA_DIR, '.refreshed')
UPDATED_FLAG_FILE = os.path.join(DATA_DIR, '.updated')

# Ensure directories exist
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

def looks_like_url(text):
    """
    Check if a string looks like a URL
    """
    if not text:
        return False
    # Simple check for common URL patterns
    url_patterns = ['http://', 'https://', 'www.']
    return any(pattern in text.lower() for pattern in url_patterns)

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

def are_events_duplicates(event1, event2):
    """
    Check if two events are likely duplicates based on title, date, and time
    
    Args:
        event1: First event dictionary
        event2: Second event dictionary
        
    Returns:
        True if events are likely duplicates, False otherwise
    """
    # Compare normalized titles (case-insensitive, stripped)
    title1 = event1.get('title', '').strip().lower()
    title2 = event2.get('title', '').strip().lower()
    
    # Compare dates and times
    date1 = event1.get('date', '')
    date2 = event2.get('date', '')
    time1 = event1.get('time', '')
    time2 = event2.get('time', '')
    
    # Events are duplicates if they have the same title, date, and time
    return (title1 == title2 and date1 == date2 and time1 == time2)

def remove_duplicates(events):
    """
    Remove duplicate events from a list
    
    Args:
        events: List of event dictionaries
        
    Returns:
        List of events with duplicates removed
    """
    unique_events = []
    
    for event in events:
        # Check if this event is a duplicate of any existing event
        is_duplicate = False
        for existing_event in unique_events:
            if are_events_duplicates(event, existing_event):
                is_duplicate = True
                print(f"Removing duplicate event: {event.get('title', 'Unknown')} on {event.get('date', 'Unknown')}")
                break
        
        if not is_duplicate:
            unique_events.append(event)
    
    return unique_events

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
        
        # If location looks like a URL and we don't have a URL yet, use it as the URL
        if not event_url and looks_like_url(event_location):
            event_url = event_location
            event_location = ''  # Clear the location since we're using it as URL
        
        # If still no URL, try fallback URL from group
        if not event_url and group and group.get('fallback_url'):
            event_url = sanitize_text(group.get('fallback_url'))
            
        # If there's still no URL, skip this event
        if not event_url:
            return None
        
        # Create the event dictionary
        event_dict = {
            'title': event_summary,
            'description': event_description,
            'location': normalize_address(event_location),
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
            with open(file_path, 'r', encoding='utf-8') as f:
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
            with open(file_path, 'r', encoding='utf-8') as f:
                event = yaml.safe_load(f)
                # Add the event ID (filename without extension)
                event['id'] = os.path.splitext(os.path.basename(file_path))[0]
                
                # Normalize location if present
                if 'location' in event:
                    event['location'] = normalize_address(event['location'])
                
                # Map submitted_by to submitter_name and submitter_link
                if 'submitted_by' in event:
                    if event['submitted_by'].lower() != 'anonymous':
                        event['submitter_name'] = event['submitted_by']
                        if 'submitter_link' in event:
                            event['submitter_link'] = event['submitter_link']
                
                # Parse date and time using dateparser
                if 'date' in event and 'time' in event:
                    # First normalize the date to YYYY-MM-DD format
                    if isinstance(event['date'], date):
                        event['date'] = event['date'].strftime('%Y-%m-%d')
                    else:
                        # Parse the date string flexibly
                        parsed_date = dateparser.parse(str(event['date']), settings={
                            'TIMEZONE': timezone_name,
                            'DATE_ORDER': 'YMD',
                            'PREFER_DATES_FROM': 'future',
                            'PREFER_DAY_OF_MONTH': 'first'
                        })
                        if parsed_date is None:
                            raise ValueError(f"Could not parse date: {event['date']}")
                        event['date'] = parsed_date.strftime('%Y-%m-%d')
                    
                    # Now handle the time
                    try:
                        if isinstance(event['time'], int):
                            # Handle integer time format (e.g., 1000 for 10:00)
                            time_str = str(event['time']).zfill(4)
                            hours = int(time_str[:-2])
                            minutes = int(time_str[-2:])
                            if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                                raise ValueError
                            event['time'] = f"{hours:02d}:{minutes:02d}"
                        else:
                            # Try to parse as HH:MM format first
                            try:
                                hours, minutes = map(int, str(event['time']).split(':'))
                                if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                                    raise ValueError
                                event['time'] = f"{hours:02d}:{minutes:02d}"
                            except (ValueError, TypeError):
                                # If that fails, try flexible parsing
                                parsed_time = dateparser.parse(str(event['time']), settings={
                                    'TIMEZONE': timezone_name,
                                    'RETURN_AS_TIMEZONE_AWARE': True
                                })
                                if parsed_time is None:
                                    raise ValueError(f"Could not parse time: {event['time']}")
                                event['time'] = parsed_time.strftime('%H:%M')
                    except (ValueError, TypeError) as e:
                        raise ValueError(f"Invalid time format: {event['time']}")

                    # Combine date and time for full datetime
                    event_datetime = dateparser.parse(f"{event['date']} {event['time']}", settings={
                        'TIMEZONE': timezone_name,
                        'RETURN_AS_TIMEZONE_AWARE': True,
                        'DATE_ORDER': 'YMD',
                        'PREFER_DATES_FROM': 'future'
                    })
                    
                    if event_datetime is None:
                        raise ValueError(f"Could not parse combined date/time: {event['date']} {event['time']}")
                    
                    # Set standardized fields
                    event['start_date'] = event_datetime.strftime('%Y-%m-%d')
                    event['start_time'] = event_datetime.strftime('%H:%M')
                    
                    # Handle end date/time
                    if 'end_date' in event and 'end_time' in event:
                        # Normalize end date
                        if isinstance(event['end_date'], date):
                            event['end_date'] = event['end_date'].strftime('%Y-%m-%d')
                        else:
                            parsed_end_date = dateparser.parse(str(event['end_date']), settings={
                                'TIMEZONE': timezone_name,
                                'DATE_ORDER': 'YMD',
                                'PREFER_DATES_FROM': 'future'
                            })
                            if parsed_end_date is None:
                                event['end_date'] = event['date']  # Use start date if can't parse
                            else:
                                event['end_date'] = parsed_end_date.strftime('%Y-%m-%d')
                        
                        # Parse end time
                        try:
                            if isinstance(event['end_time'], int):
                                time_str = str(event['end_time']).zfill(4)
                                hours = int(time_str[:-2])
                                minutes = int(time_str[-2:])
                                if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                                    raise ValueError
                                event['end_time'] = f"{hours:02d}:{minutes:02d}"
                            else:
                                parsed_time = dateparser.parse(str(event['end_time']), settings={
                                    'TIMEZONE': timezone_name,
                                    'RETURN_AS_TIMEZONE_AWARE': True
                                })
                                if parsed_time is None:
                                    event['end_time'] = event['time']  # Use start time if can't parse
                                else:
                                    event['end_time'] = parsed_time.strftime('%H:%M')
                        except (ValueError, TypeError):
                            event['end_time'] = event['time']  # Use start time if invalid
                        
                        # Validate combined end date/time
                        end_datetime = dateparser.parse(f"{event['end_date']} {event['end_time']}", settings={
                            'TIMEZONE': timezone_name,
                            'RETURN_AS_TIMEZONE_AWARE': True,
                            'DATE_ORDER': 'YMD',
                            'PREFER_DATES_FROM': 'future'
                        })
                        if end_datetime is None:
                            end_datetime = event_datetime
                    else:
                        # Only set end_date and end_time if they were explicitly provided
                        if 'end_date' in event and 'end_time' in event:
                            event['end_date'] = end_datetime.strftime('%Y-%m-%d')
                            event['end_time'] = end_datetime.strftime('%H:%M')
                
                events.append(event)
        except Exception as e:
            print(f"Error loading event from {file_path}: {str(e)}")
    
    return events

def calculate_stats(groups, all_events):
    """
    Calculate statistics about events and groups
    
    Args:
        groups: List of all groups
        all_events: List of all events
        
    Returns:
        Dictionary containing stats
    """
    # Count active groups
    active_groups = len([g for g in groups if g.get('active', True)])
    
    # Get current date
    today = datetime.now(local_tz).date()
    
    # Count all future events
    upcoming_event_count = len([
        event for event in all_events 
        if dateparser.parse(event['date'], settings={
            'TIMEZONE': timezone_name,
            'DATE_ORDER': 'YMD'
        }).date() >= today
    ])
    
    return {
        'upcoming_events': upcoming_event_count,
        'active_groups': active_groups
    }

def generate_yaml():
    """
    Generate YAML files from iCal and single events
    
    Returns:
        True if any YAML files were updated, False otherwise
    """
    print("Generating YAML files...")
    
    # Get current date at the start
    today = datetime.now(local_tz).date()
    
    # Calculate date 90 days from now
    max_future_date = today + timedelta(days=90)
    
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

        # Check for iCal with JSON-LD augmentation
        if 'ical' in group and group['ical']:
            cache_file = os.path.join(ICAL_CACHE_DIR, f"{group['id']}.json")
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r') as f:
                        events = json.load(f)
                        group_events = []
                        for event in events:
                            # Check if event URL is in suppress_urls list
                            suppress_urls = group.get('suppress_urls', [])
                            if event.get('url') not in suppress_urls:
                                # Add group information
                                event['group'] = str(group.get('name', ''))
                                event['group_website'] = str(group.get('website', ''))
                                # For iCal+JSON-LD events, apply 90-day limit
                                event_date = dateparser.parse(event['date'], settings={
                                    'TIMEZONE': timezone_name,
                                    'DATE_ORDER': 'YMD'
                                }).date()
                                if today <= event_date <= max_future_date:
                                    group_events.append(event)

                        # Remove duplicates within this group's events
                        group_events = remove_duplicates(group_events)
                        all_events.extend(group_events)
                except Exception as e:
                    print(f"Error processing iCal+JSON-LD events for group {group['id']}: {str(e)}")

    
    # Add single events (include all future events regardless of date)
    for event in single_events:
        event_date = dateparser.parse(event['date'], settings={
            'TIMEZONE': timezone_name,
            'DATE_ORDER': 'YMD'
        }).date()
        if today <= event_date:  # Only check that event is in the future
            all_events.append(event)
    
    # Remove duplicates across all events (keeps first occurrence)
    all_events = remove_duplicates(all_events)
    
    # Sort events by date and time
    all_events.sort(key=lambda x: (str(x.get('date', '')), str(x.get('time', ''))))
    
    # Get current month and year
    current_month = today.month
    current_year = today.year
    
    # Calculate next month
    if current_month == 12:
        next_month = 1
        next_year = current_year + 1
    else:
        next_month = current_month + 1
        next_year = current_year
    
    # Write all events to upcoming.yaml
    upcoming_file = os.path.join(DATA_DIR, 'upcoming.yaml')
    with open(upcoming_file, 'w', encoding='utf-8') as f:
        yaml.dump(all_events, f, sort_keys=False, allow_unicode=True)
    
    # Generate and write stats.yaml
    stats = calculate_stats(groups, all_events)
    stats_file = os.path.join(DATA_DIR, 'stats.yaml')
    with open(stats_file, 'w', encoding='utf-8') as f:
        yaml.dump(stats, f, sort_keys=False, allow_unicode=True)
    
    # Create a flag file to indicate that YAML files were updated
    with open(UPDATED_FLAG_FILE, 'w', encoding='utf-8') as f:
        f.write(datetime.now().isoformat())
    
    print("YAML files updated successfully")
    return True

def main():
    """
    Main function to generate month data
    """
    # Create data directory if it doesn't exist
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Generate YAML files
    generate_yaml()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())