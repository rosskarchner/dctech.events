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
                
                # Parse date and time using dateparser
                if 'date' in event and 'time' in event:
                    # Convert date to string if it's a date object
                    if isinstance(event['date'], date):
                        event['date'] = event['date'].strftime('%Y-%m-%d')
                    
                    # Parse the date and time using dateparser
                    # First try to parse time in standard format HH:MM or as integer
                    try:
                        if isinstance(event['time'], int):
                            # Handle integer time format (e.g., 1000 for 10:00)
                            time_str = str(event['time']).zfill(4)
                            hours = int(time_str[:-2])
                            minutes = int(time_str[-2:])
                        else:
                            # Handle HH:MM string format
                            hours, minutes = map(int, str(event['time']).split(':'))
                        
                        if 0 <= hours <= 23 and 0 <= minutes <= 59:
                            # Time is in valid format, use it directly
                            event_datetime_str = f"{event['date']} {hours:02d}:{minutes:02d}"
                            event_datetime = dateparser.parse(event_datetime_str, settings={
                                'TIMEZONE': timezone_name,
                                'RETURN_AS_TIMEZONE_AWARE': True,
                                'DATE_ORDER': 'YMD',
                                'PREFER_DATES_FROM': 'future',
                                'PREFER_DAY_OF_MONTH': 'first'
                            })
                        else:
                            raise ValueError
                    except (ValueError, TypeError):
                        # If not standard format, try flexible parsing
                        event_datetime_str = f"{event['date']} {event['time']}"
                        event_datetime = dateparser.parse(event_datetime_str, settings={
                            'TIMEZONE': timezone_name,
                            'RETURN_AS_TIMEZONE_AWARE': True,
                            'DATE_ORDER': 'YMD',
                            'PREFER_DATES_FROM': 'future',
                            'PREFER_DAY_OF_MONTH': 'first'
                        })
                    
                    if event_datetime is None:
                        raise ValueError(f"Could not parse date/time: {event_datetime_str}")
                    
                    # Add formatted fields
                    event['start_date'] = event_datetime.strftime('%Y-%m-%d')
                    event['start_time'] = event_datetime.strftime('%H:%M')
                    
                    # Handle end date/time
                    if 'end_date' in event and 'end_time' in event:
                        end_datetime = dateparser.parse(f"{event['end_date']} {event['end_time']}", settings={
                            'TIMEZONE': timezone_name,
                            'RETURN_AS_TIMEZONE_AWARE': True,
                            'DATE_ORDER': 'YMD',
                            'PREFER_DATES_FROM': 'future',
                            'PREFER_DAY_OF_MONTH': 'first'
                        })
                        if end_datetime is None:
                            end_datetime = event_datetime
                    else:
                        end_datetime = event_datetime
                        
                    event['end_date'] = end_datetime.strftime('%Y-%m-%d')
                    event['end_time'] = end_datetime.strftime('%H:%M')
                
                events.append(event)
        except Exception as e:
            print(f"Error loading event from {file_path}: {str(e)}")
    
    return events

def generate_yaml():
    """
    Generate YAML files from iCal and single events
    
    Returns:
        True if any YAML files were updated, False otherwise
    """
    print("Generating YAML files...")
    
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
        # Parse date using dateparser for consistency
        event_date_str = event.get('date')
        if isinstance(event_date_str, date):
            event_date = event_date_str
        else:
            parsed_date = dateparser.parse(event_date_str, settings={
                'TIMEZONE': timezone_name,
                'DATE_ORDER': 'YMD',
                'PREFER_DATES_FROM': 'future'
            })
            if parsed_date is None:
                print(f"Warning: Could not parse date: {event_date_str}")
                continue
            event_date = parsed_date.date()
        
        # Include if event is today or later and in current or next month
        if event_date >= today and (
            (event_date.year == current_year and event_date.month == current_month) or
            (event_date.year == next_year and event_date.month == next_month)
        ):
            upcoming_events.append(event)
    
    # Group events by month for per-month files
    events_by_month = {}
    for event in all_events:
        # Parse date using dateparser for consistency
        event_date_str = event.get('date')
        if isinstance(event_date_str, date):
            event_date = event_date_str
        else:
            parsed_date = dateparser.parse(event_date_str, settings={
                'TIMEZONE': timezone_name,
                'DATE_ORDER': 'YMD',
                'PREFER_DATES_FROM': 'future'
            })
            if parsed_date is None:
                print(f"Warning: Could not parse date: {event_date_str}")
                continue
            event_date = parsed_date.date()
            
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
    
    # Create a flag file to indicate that YAML files were updated
    with open(UPDATED_FLAG_FILE, 'w') as f:
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