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
import hashlib
from location_utils import extract_location_info

# Load configuration
CONFIG_FILE = 'config.yaml'
config = {}
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r') as f:
        config = yaml.safe_load(f)

# Initialize timezone from config
timezone_name = config.get('timezone', 'US/Eastern')
local_tz = pytz.timezone(timezone_name)

# Get site-wide only_states filter (applies to iCal feeds only)
ALLOWED_STATES = config.get('only_states', [])

# Constants - data paths
GROUPS_DIR = '_groups'
SINGLE_EVENTS_DIR = '_single_events'
CATEGORIES_DIR = '_categories'
DATA_DIR = '_data'
CACHE_DIR = '_cache'  # Shared cache directory
ICAL_CACHE_DIR = os.path.join(CACHE_DIR, 'ical')
EVENT_OVERRIDES_DIR = '_event_overrides'
REFRESH_FLAG_FILE = os.path.join(DATA_DIR, '.refreshed')
UPDATED_FLAG_FILE = os.path.join(DATA_DIR, '.updated')

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)

# Constants for location filtering
US_STATE_CODES = [
    'DC', 'MD', 'VA', 'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 
    'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MA', 'MI', 
    'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY', 'NC', 'ND', 
    'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'WA', 
    'WV', 'WI', 'WY'
]

# Compile state matching regex pattern once
STATE_PATTERN = re.compile(r'\b(' + '|'.join(US_STATE_CODES) + r')\b', re.IGNORECASE)

# Common typos for DC state code
DC_TYPO_CODES = ['DI', 'CD', 'D', 'C']

# Custom YAML representer for icalendar.prop.vText objects
def represent_vtext(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', str(data))

# Custom YAML representer for icalendar.prop.vUri objects
def represent_vuri(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', str(data))

# Register the custom representers with PyYAML
yaml.add_representer(icalendar.prop.vText, represent_vtext)
yaml.add_representer(icalendar.prop.vUri, represent_vuri)

def calculate_event_hash(date, time, title, url=None):
    """
    Calculate MD5 hash for event identification.
    Matches iCal GUID generation algorithm.

    Args:
        date: Event date (YYYY-MM-DD format)
        time: Event time (HH:MM format, or empty string)
        title: Event title
        url: Optional event URL

    Returns:
        MD5 hash string (hex)
    """
    uid_parts = [date, time, title]
    if url:
        uid_parts.append(url)

    uid_base = '-'.join(str(p) for p in uid_parts)
    uid_hash = hashlib.md5(uid_base.encode('utf-8')).hexdigest()
    return uid_hash

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

def is_event_in_allowed_states(event, allowed_states):
    """
    Check if an event's location is in one of the allowed states
    
    Args:
        event: Event dictionary with location field
        allowed_states: List of allowed state codes (e.g., ['DC', 'MD', 'VA'])
        
    Returns:
        True if event is in an allowed state or state is unclear, False if clearly in a different state
    """
    if not allowed_states:
        return True  # No filter applied
    
    location = event.get('location', '')
    if not location:
        return True  # Allow events with no location
    
    # First try the structured extraction
    city, state = extract_location_info(location)
    
    if state:
        # If we successfully extracted a state code
        if state in US_STATE_CODES:
            # It's a valid state code, check if it's in allowed list
            return state in allowed_states
        else:
            # Invalid state code - check if it's likely a DC typo
            # Only assume DC if: (1) DC is in allowed states, AND
            # (2) either the city is Washington or state looks like a DC typo
            if 'DC' in allowed_states:
                # If city is Washington, any invalid state -> assume DC
                if city and city.lower() == 'washington':
                    return True
                # Otherwise check if state looks like a common DC typo
                elif state.upper() in DC_TYPO_CODES:
                    return True
            # Invalid state, not a DC typo -> filter out
            return False
    
    # If structured extraction didn't work, try regex to find state codes
    matches = STATE_PATTERN.findall(location)
    
    if matches:
        # Convert to uppercase and check against allowed states
        found_states = [s.upper() for s in matches]
        for found_state in found_states:
            if found_state in allowed_states:
                return True
        # If we found states but none are in allowed list, reject
        return False
    
    # If no state found, allow it (state is unclear - could be virtual, international, or unparseable)
    return True

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
    Remove duplicate events from a list, rolling up cross-posted events
    
    When the same event is posted to multiple groups, keep the first occurrence
    and add an 'also_published_by' field with info about the other groups.
    
    Events marked with 'duplicate_of' field are treated as explicit duplicates
    and rolled up to the event they reference (if found).
    
    Args:
        events: List of event dictionaries
        
    Returns:
        List of events with duplicates removed and cross-posting info added
    """
    # Separate explicit duplicates from regular events
    explicit_duplicates = [e for e in events if e.get('duplicate_of')]
    regular_events = [e for e in events if not e.get('duplicate_of')]
    
    unique_events = []
    
    # First, process regular events (auto-detect duplicates)
    for event in regular_events:
        # Check if this event is a duplicate of any existing event (automatic detection)
        is_duplicate = False
        for existing_event in unique_events:
            if are_events_duplicates(event, existing_event):
                is_duplicate = True
                
                # Add cross-posting information to the existing event
                if 'also_published_by' not in existing_event:
                    existing_event['also_published_by'] = []
                
                # Add this group's info if it has group information
                if event.get('group') and event.get('group_website'):
                    existing_event['also_published_by'].append({
                        'group': event['group'],
                        'group_website': event['group_website'],
                        'url': event.get('url', '')
                    })
                    print(f"Rolling up duplicate event: {event.get('title', 'Unknown')} on {event.get('date', 'Unknown')} (also by {event['group']})")
                else:
                    print(f"Removing duplicate event: {event.get('title', 'Unknown')} on {event.get('date', 'Unknown')}")
                
                break
        
        if not is_duplicate:
            unique_events.append(event)
    
    # Now process explicit duplicates
    for event in explicit_duplicates:
        duplicate_of_guid = event['duplicate_of']
        # Find the event it's a duplicate of
        parent_event = None
        for existing_event in unique_events:
            if existing_event.get('guid') == duplicate_of_guid:
                parent_event = existing_event
                break
        
        if parent_event:
            # Parent found - roll up to it
            # Add cross-posting information to the parent event
            if 'also_published_by' not in parent_event:
                parent_event['also_published_by'] = []
            
            # Add this event's group info if available
            if event.get('group') and event.get('group_website'):
                parent_event['also_published_by'].append({
                    'group': event['group'],
                    'group_website': event['group_website'],
                    'url': event.get('url', '')
                })
                print(f"Rolling up duplicate event: {event.get('title', 'Unknown')} on {event.get('date', 'Unknown')} (also by {event['group']})")
            else:
                print(f"Removing duplicate event: {event.get('title', 'Unknown')} on {event.get('date', 'Unknown')}")
        else:
            # Parent not found in current list - keep this event for later processing
            # This happens when processing per-group and the parent is in a different group
            unique_events.append(event)
    
    return unique_events

def load_groups():
    """
    Load all groups from the _groups directory

    Returns:
        A list of group dictionaries
    """
    groups = []

    # Load groups from local _groups directory
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

    # Load events from local _single_events directory
    for file_path in glob.glob(os.path.join(SINGLE_EVENTS_DIR, '*.yaml')):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                event_data = yaml.safe_load(f)
                
            event_id = os.path.splitext(os.path.basename(file_path))[0]
            parsed_event = parse_single_event_data(event_data, event_id, timezone_name)
            
            if parsed_event:
                events.append(parsed_event)
        except Exception as e:
            print(f"Error loading event from {file_path}: {str(e)}")

    return events

def parse_single_event_data(event, event_id, timezone_name):
    """
    Parse a single event dictionary, normalizing dates and times.
    
    Args:
        event: Raw event dictionary from YAML
        event_id: ID for the event (filename)
        timezone_name: Timezone string to use for parsing
        
    Returns:
        Processed event dictionary or None if parsing failed
    """
    # Add the event ID
    event['id'] = event_id

    # Parse date and time using dateparser
    if 'date' in event and 'time' in event and event['time']:
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
        # Skip time validation if it's a dictionary (per-day times for multi-day events)
        if isinstance(event['time'], dict):
            # Validate each time in the dictionary
            for day_key, day_time in event['time'].items():
                try:
                    if isinstance(day_time, int):
                        # Handle integer time format (e.g., 1000 for 10:00)
                        time_str = str(day_time).zfill(4)
                        hours = int(time_str[:-2])
                        minutes = int(time_str[-2:])
                        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                            raise ValueError
                        event['time'][day_key] = f"{hours:02d}:{minutes:02d}"
                    else:
                        # Try to parse as HH:MM format first
                        hours, minutes = map(int, str(day_time).split(':'))
                        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                            raise ValueError
                        event['time'][day_key] = f"{hours:02d}:{minutes:02d}"
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid time format for {day_key}: {day_time}")
            # Keep time as dictionary, skip combined date/time parsing
            # events.append will happen at the end of the try block
        else:
            # Process regular time (not a dictionary)
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

    elif 'date' in event:
        # Handle all-day events (date but no time)
        # Normalize the date to YYYY-MM-DD format
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

        # Set start_date for all-day events (no start_time since no time specified)
        event['start_date'] = event['date']

        # Handle end_date if present
        if 'end_date' in event:
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
        else:
            event['end_date'] = event['date']

    return event

def load_categories():
    """
    Load all categories from the _categories directory

    Returns:
        A dictionary mapping category slugs to category metadata
    """
    categories = {}

    # Load categories from local _categories directory
    for file_path in glob.glob(os.path.join(CATEGORIES_DIR, '*.yaml')):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                category = yaml.safe_load(f)
                # Get the category slug (filename without extension)
                slug = os.path.splitext(os.path.basename(file_path))[0]
                category['slug'] = slug
                categories[slug] = category
        except Exception as e:
            print(f"Error loading category from {file_path}: {str(e)}")

    return categories


def load_event_override(event_hash):
    """
    Load an event override file if it exists.

    Args:
        event_hash: MD5 hash identifying the event

    Returns:
        Dictionary with override data, or None if no override exists
    """
    override_file = os.path.join(EVENT_OVERRIDES_DIR, f"{event_hash}.yaml")
    if os.path.exists(override_file):
        try:
            with open(override_file, 'r', encoding='utf-8') as f:
                override = yaml.safe_load(f)
                return override if override else None
        except Exception as e:
            print(f"Error loading override from {override_file}: {str(e)}")
    return None


def merge_event_with_override(event, override):
    """
    Merge an event with its override data. Override fields take precedence.

    Args:
        event: Original event dictionary
        override: Override data dictionary

    Returns:
        Merged event dictionary
    """
    if not override:
        return event

    merged = event.copy()
    # Override fields take precedence
    for key, value in override.items():
        if value is not None:
            merged[key] = value
    return merged

def resolve_event_categories(event, group, categories):
    """
    Resolve categories for an event based on event-level and group-level categories.

    Priority:
    1. Event-specific categories (if present)
    2. Group categories (if event doesn't have categories)
    3. Empty list (if neither has categories)

    Args:
        event: Event dictionary
        group: Group dictionary (or None for single events)
        categories: Dictionary of valid categories

    Returns:
        List of category slugs (empty list if none)
    """
    # Check if event has categories
    if 'categories' in event and event['categories']:
        event_cats = event['categories']
        # Ensure it's a list
        if not isinstance(event_cats, list):
            event_cats = [event_cats]
        # Filter to only valid categories
        return [cat for cat in event_cats if cat in categories]

    # Check if group has categories
    if group and 'categories' in group and group['categories']:
        group_cats = group['categories']
        # Ensure it's a list
        if not isinstance(group_cats, list):
            group_cats = [group_cats]
        # Filter to only valid categories
        return [cat for cat in group_cats if cat in categories]

    # No categories found
    return []

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

def process_events(groups, categories, single_events, ical_events_map, allowed_states=None, today=None):
    """
    Process events from all sources, filter, deduplicate, and prepare for output.
    
    Args:
        groups: List of group dictionaries
        categories: Dictionary of categories
        single_events: List of single event dictionaries
        ical_events_map: Dictionary mapping group ID to list of cached iCal events
        allowed_states: List of allowed state codes
        today: Date to use as 'today' for filtering (optional)
        
    Returns:
        List of processed and sorted events
    """
    if allowed_states is None:
        allowed_states = []
        
    # Get current date if not provided
    if today is None:
        today = datetime.now(local_tz).date()
    # Calculate date 90 days from now
    max_future_date = today + timedelta(days=90)
    
    all_events = []
    
    # Process iCal events
    for group in groups:
        if not group.get('active', True):
            continue

        if group['id'] in ical_events_map:
            try:
                events = ical_events_map[group['id']]
                group_events = []
                for event in events:
                    # Check if event URL is in suppress_urls list
                    suppress_urls = group.get('suppress_urls', [])

                    # Calculate event GUID hash for suppress_guid check
                    event_hash = calculate_event_hash(
                        event.get('date', ''),
                        event.get('time', ''),
                        event.get('title', ''),
                        event.get('url')
                    )
                    suppress_guids = group.get('suppress_guid', [])

                    # Skip event if URL or GUID is suppressed
                    if event.get('url') not in suppress_urls and event_hash not in suppress_guids:
                        # Apply site-wide state filter for iCal events
                        if is_event_in_allowed_states(event, allowed_states):
                            # Check for event override and merge if exists
                            override = load_event_override(event_hash)
                            if override:
                                event = merge_event_with_override(event, override)
                            
                            # Add group information
                            event['group'] = str(group.get('name', ''))
                            event['group_website'] = str(group.get('website', ''))
                            
                            # Mark source as 'ical'
                            event['source'] = 'ical'
                            event['guid'] = event_hash
                            
                            # Resolve and add categories
                            event_categories = resolve_event_categories(event, group, categories)
                            if event_categories:
                                event['categories'] = event_categories
                            # For iCal+JSON-LD events, apply 90-day limit
                            try:
                                event_date = dateparser.parse(event['date'], settings={
                                    'TIMEZONE': timezone_name,
                                    'DATE_ORDER': 'YMD'
                                }).date()
                                if today <= event_date <= max_future_date:
                                    group_events.append(event)
                            except (ValueError, AttributeError):
                                pass # Skip events with invalid dates
                        else:
                            print(f"Filtering out event '{event.get('title', 'Unknown')}' - location '{event.get('location', 'Unknown')}' not in allowed states {allowed_states}")

                # Remove duplicates within this group's events
                group_events = remove_duplicates(group_events)
                all_events.extend(group_events)
            except Exception as e:
                print(f"Error processing iCal+JSON-LD events for group {group['id']}: {str(e)}")

    # Add single events (include all future events regardless of date)
    for event in single_events:
        try:
            event_date = dateparser.parse(event['date'], settings={
                'TIMEZONE': timezone_name,
                'DATE_ORDER': 'YMD'
            }).date()
            if today <= event_date:  # Only check that event is in the future
                # Find the group for this event if it has one
                event_group = None
                if 'group' in event and event['group']:
                    # Try to find the group by name
                    for group in groups:
                        if group.get('name', '') == event['group']:
                            event_group = group
                            break
                
                # Calculate event hash for single events
                event_hash = calculate_event_hash(
                    event.get('date', ''),
                    event.get('time', ''),
                    event.get('title', ''),
                    event.get('url')
                )
                
                # Check for event override and merge if exists
                override = load_event_override(event_hash)
                if override:
                    event = merge_event_with_override(event, override)
                
                # Mark source as 'manual'
                event['source'] = 'manual'
                event['guid'] = event_hash
                
                # Resolve and add categories
                event_categories = resolve_event_categories(event, event_group, categories)
                if event_categories:
                    event['categories'] = event_categories
                all_events.append(event)
        except (ValueError, AttributeError):
            pass

    # Remove duplicates across all events (keeps first occurrence)
    all_events = remove_duplicates(all_events)
    
    # Sort events by date and time
    all_events.sort(key=lambda x: (str(x.get('date', '')), str(x.get('time', ''))))
    
    return all_events

def generate_yaml():
    """
    Generate YAML files from iCal and single events
    
    Returns:
        True if any YAML files were updated, False otherwise
    """
    print("Generating YAML files...")

    # Load all groups
    groups = load_groups()

    # Load all categories
    categories = load_categories()

    # Load all single events
    single_events = load_single_events()
    
    # Load ical events cache
    ical_events_map = {}
    for group in groups:
        if not group.get('active', True):
            continue
            
        if 'ical' in group and group['ical']:
            cache_file = os.path.join(ICAL_CACHE_DIR, f"{group['id']}.json")
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r') as f:
                        ical_events_map[group['id']] = json.load(f)
                except Exception as e:
                    print(f"Error loading cache for group {group['id']}: {str(e)}")
    
    # Process events
    all_events = process_events(groups, categories, single_events, ical_events_map, ALLOWED_STATES)
    
    # Write all events to upcoming.yaml
    upcoming_file = os.path.join(DATA_DIR, 'upcoming.yaml')
    with open(upcoming_file, 'w', encoding='utf-8') as f:
        yaml.dump(all_events, f, sort_keys=False, allow_unicode=True)

    # Write all events to events.json for client-side use
    events_json_file = os.path.join(DATA_DIR, 'events.json')
    with open(events_json_file, 'w', encoding='utf-8') as f:
        json.dump(all_events, f, indent=2, ensure_ascii=False)

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