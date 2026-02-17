#!/usr/bin/env python3
import os
import yaml
import icalendar
import pytz
from datetime import datetime, timedelta, timezone, date
import re
from pathlib import Path
import sys
import calendar as cal_module
import dateparser
import json
import hashlib
from location_utils import extract_location_info
import db_utils
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

# Get site-wide only_states filter (applies to iCal feeds only)
ALLOWED_STATES = config.get('only_states', [])

# Constants - data paths
DATA_DIR = '_data'
CACHE_DIR = '_cache'  # Shared cache directory
ICAL_CACHE_DIR = os.path.join(CACHE_DIR, 'ical')
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

# Common typos for DC state code (limited to 2-character codes to avoid false positives)
DC_TYPO_CODES = ['DI', 'CD']

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
    """
    uid_parts = [date, time, title]
    if url:
        uid_parts.append(url)

    uid_base = '-'.join(str(p) for p in uid_parts)
    uid_hash = hashlib.md5(uid_base.encode('utf-8')).hexdigest()
    return uid_hash

def is_event_in_allowed_states(event, allowed_states):
    """
    Check if an event's location is in one of the allowed states
    """
    if not allowed_states:
        return True
    
    location = event.get('location', '')
    if not location:
        return True
    
    city, state = extract_location_info(location)
    
    if state:
        if state in US_STATE_CODES:
            return state in allowed_states
        else:
            if 'DC' in allowed_states:
                if city and city.lower() == 'washington':
                    return True
                if state in DC_TYPO_CODES:
                    return True
            return False
    
    matches = STATE_PATTERN.findall(location)
    if matches:
        found_states = [s.upper() for s in matches]
        for found_state in found_states:
            if found_state in allowed_states:
                return True
        return False
    
    return True

def are_events_duplicates(event1, event2):
    """
    Check if two events are likely duplicates based on title, date, and time
    """
    title1 = event1.get('title', '').strip().lower()
    title2 = event2.get('title', '').strip().lower()
    date1 = event1.get('date', '')
    date2 = event2.get('date', '')
    time1 = event1.get('time', '')
    time2 = event2.get('time', '')
    return (title1 == title2 and date1 == date2 and time1 == time2)

def remove_duplicates(events):
    """
    Remove duplicate events from a list, rolling up cross-posted events
    """
    explicit_duplicates = [e for e in events if e.get('duplicate_of')]
    regular_events = [e for e in events if not e.get('duplicate_of')]
    unique_events = []
    
    for event in regular_events:
        is_duplicate = False
        for existing_event in unique_events:
            if are_events_duplicates(event, existing_event):
                is_duplicate = True
                if 'also_published_by' not in existing_event:
                    existing_event['also_published_by'] = []
                if event.get('group') and event.get('group_website'):
                    existing_event['also_published_by'].append({
                        'group': event['group'],
                        'group_website': event['group_website'],
                        'url': event.get('url', '')
                    })
                break
        
        if not is_duplicate:
            unique_events.append(event)
    
    for event in explicit_duplicates:
        duplicate_of_guid = event['duplicate_of']
        parent_event = None
        for existing_event in unique_events:
            if existing_event.get('guid') == duplicate_of_guid:
                parent_event = existing_event
                break
        
        if parent_event:
            if 'also_published_by' not in parent_event:
                parent_event['also_published_by'] = []
            if event.get('group') and event.get('group_website'):
                parent_event['also_published_by'].append({
                    'group': event['group'],
                    'group_website': event['group_website'],
                    'url': event.get('url', '')
                })
        else:
            unique_events.append(event)
    
    return unique_events

def parse_single_event_data(event, event_id, timezone_name):
    """
    Parse a single event dictionary, normalizing dates and times.
    """
    event['id'] = event_id

    if 'date' in event and 'time' in event and event['time']:
        if isinstance(event['date'], date):
            event['date'] = event['date'].strftime('%Y-%m-%d')
        else:
            parsed_date = dateparser.parse(str(event['date']), settings={
                'TIMEZONE': timezone_name,
                'DATE_ORDER': 'YMD',
                'PREFER_DATES_FROM': 'future',
                'PREFER_DAY_OF_MONTH': 'first'
            })
            if parsed_date is None:
                raise ValueError(f"Could not parse date: {event['date']}")
            event['date'] = parsed_date.strftime('%Y-%m-%d')
        
        if isinstance(event['time'], dict):
            for day_key, day_time in event['time'].items():
                try:
                    if isinstance(day_time, int):
                        time_str = str(day_time).zfill(4)
                        hours = int(time_str[:-2])
                        minutes = int(time_str[-2:])
                        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                            raise ValueError
                        event['time'][day_key] = f"{hours:02d}:{minutes:02d}"
                    else:
                        hours, minutes = map(int, str(day_time).split(':'))
                        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                            raise ValueError
                        event['time'][day_key] = f"{hours:02d}:{minutes:02d}"
                except (ValueError, TypeError):
                    raise ValueError(f"Invalid time format for {day_key}: {day_time}")
        else:
            try:
                if isinstance(event['time'], int):
                    time_str = str(event['time']).zfill(4)
                    hours = int(time_str[:-2])
                    minutes = int(time_str[-2:])
                    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                        raise ValueError
                    event['time'] = f"{hours:02d}:{minutes:02d}"
                else:
                    try:
                        hours, minutes = map(int, str(event['time']).split(':'))
                        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                            raise ValueError
                        event['time'] = f"{hours:02d}:{minutes:02d}"
                    except (ValueError, TypeError):
                        parsed_time = dateparser.parse(str(event['time']), settings={
                            'TIMEZONE': timezone_name,
                            'RETURN_AS_TIMEZONE_AWARE': True
                        })
                        if parsed_time is None:
                            raise ValueError(f"Could not parse time: {event['time']}")
                        event['time'] = parsed_time.strftime('%H:%M')
            except (ValueError, TypeError):
                raise ValueError(f"Invalid time format: {event['time']}")

            event_datetime = dateparser.parse(f"{event['date']} {event['time']}", settings={
                'TIMEZONE': timezone_name,
                'RETURN_AS_TIMEZONE_AWARE': True,
                'DATE_ORDER': 'YMD',
                'PREFER_DATES_FROM': 'future'
            })
            
            if event_datetime is None:
                raise ValueError(f"Could not parse combined date/time: {event['date']} {event['time']}")
            
            event['start_date'] = event_datetime.strftime('%Y-%m-%d')
            event['start_time'] = event_datetime.strftime('%H:%M')
        
        if 'end_date' in event and 'end_time' in event:
            if isinstance(event['end_date'], date):
                event['end_date'] = event['end_date'].strftime('%Y-%m-%d')
            else:
                parsed_end_date = dateparser.parse(str(event['end_date']), settings={
                    'TIMEZONE': timezone_name,
                    'DATE_ORDER': 'YMD',
                    'PREFER_DATES_FROM': 'future'
                })
                if parsed_end_date is None:
                    event['end_date'] = event['date']
                else:
                    event['end_date'] = parsed_end_date.strftime('%Y-%m-%d')
            
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
                        event['end_time'] = event['time']
                    else:
                        event['end_time'] = parsed_time.strftime('%H:%M')
            except (ValueError, TypeError):
                event['end_time'] = event['time']
            
            end_datetime = dateparser.parse(f"{event['end_date']} {event['end_time']}", settings={
                'TIMEZONE': timezone_name,
                'RETURN_AS_TIMEZONE_AWARE': True,
                'DATE_ORDER': 'YMD',
                'PREFER_DATES_FROM': 'future'
            })
            if end_datetime is None:
                end_datetime = event_datetime
        else:
            if 'end_date' in event and 'end_time' in event:
                event['end_date'] = end_datetime.strftime('%Y-%m-%d')
                event['end_time'] = end_datetime.strftime('%H:%M')

    elif 'date' in event:
        if isinstance(event['date'], date):
            event['date'] = event['date'].strftime('%Y-%m-%d')
        else:
            parsed_date = dateparser.parse(str(event['date']), settings={
                'TIMEZONE': timezone_name,
                'DATE_ORDER': 'YMD',
                'PREFER_DATES_FROM': 'future',
                'PREFER_DAY_OF_MONTH': 'first'
            })
            if parsed_date is None:
                raise ValueError(f"Could not parse date: {event['date']}")
            event['date'] = parsed_date.strftime('%Y-%m-%d')

        event['start_date'] = event['date']

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
                    event['end_date'] = event['date']
                else:
                    event['end_date'] = parsed_end_date.strftime('%Y-%m-%d')
        else:
            event['end_date'] = event['date']

    return event

def merge_event_with_override(event, override):
    """
    Merge an event with its override data. Override fields take precedence.
    """
    if not override:
        return event

    merged = event.copy()
    for key, value in override.items():
        if value is not None:
            merged[key] = value
    return merged

def resolve_event_categories(event, group, categories):
    """
    Resolve categories for an event based on event-level and group-level categories.
    """
    # Check if event has categories
    if 'categories' in event and event['categories']:
        event_cats = event['categories']
        if not isinstance(event_cats, list):
            event_cats = [event_cats]
        return [cat for cat in event_cats if cat in categories]

    # Check if group has categories
    if group and 'categories' in group and group['categories']:
        group_cats = group['categories']
        if not isinstance(group_cats, list):
            group_cats = [group_cats]
        return [cat for cat in group_cats if cat in categories]

    return []

def calculate_stats(groups, all_events):
    """
    Calculate statistics about events and groups
    """
    active_groups = len([g for g in groups if g.get('active', True)])
    today = datetime.now(local_tz).date()
    
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
    """
    if allowed_states is None:
        allowed_states = []
        
    if today is None:
        today = datetime.now(local_tz).date()
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
                    suppress_urls = group.get('suppress_urls', [])
                    event_hash = calculate_event_hash(
                        event.get('date', ''),
                        event.get('time', ''),
                        event.get('title', ''),
                        event.get('url')
                    )
                    suppress_guids = group.get('suppress_guid', [])

                    if event.get('url') not in suppress_urls and event_hash not in suppress_guids:
                        if is_event_in_allowed_states(event, allowed_states):
                            override = dynamo_data.get_event_override(event_hash)
                            if override:
                                event = merge_event_with_override(event, override)
                            
                            event['group'] = str(group.get('name', ''))
                            event['group_website'] = str(group.get('website', ''))
                            event['source'] = 'ical'
                            event['guid'] = event_hash
                            
                            event_categories = resolve_event_categories(event, group, categories)
                            if event_categories:
                                event['categories'] = event_categories
                            
                            try:
                                event_date = dateparser.parse(event['date'], settings={
                                    'TIMEZONE': timezone_name,
                                    'DATE_ORDER': 'YMD'
                                }).date()
                                if today <= event_date <= max_future_date:
                                    group_events.append(event)
                            except (ValueError, AttributeError):
                                pass
                
                group_events = remove_duplicates(group_events)
                all_events.extend(group_events)
            except Exception as e:
                print(f"Error processing iCal events for group {group['id']}: {str(e)}")

    # Add single events
    for event in single_events:
        try:
            event_date = dateparser.parse(event['date'], settings={
                'TIMEZONE': timezone_name,
                'DATE_ORDER': 'YMD'
            }).date()
            if today <= event_date:
                event_hash = calculate_event_hash(
                    event.get('date', ''),
                    event.get('time', ''),
                    event.get('title', ''),
                    event.get('url')
                )
                
                override = dynamo_data.get_event_override(event_hash)
                if override:
                    event = merge_event_with_override(event, override)
                
                event['source'] = 'manual'
                event['guid'] = event_hash
                
                event_group = None
                if 'group' in event and event['group']:
                    for group in groups:
                        if group.get('name', '') == event['group']:
                            event_group = group
                            break
                
                event_categories = resolve_event_categories(event, event_group, categories)
                if event_categories:
                    event['categories'] = event_categories
                all_events.append(event)
        except (ValueError, AttributeError):
            pass

    all_events = remove_duplicates(all_events)
    all_events.sort(key=lambda x: (str(x.get('date', '')), str(x.get('time', ''))))
    return all_events

def generate_yaml():
    """
    Main pipeline to refresh data and sync to DynamoDB
    """
    print("Starting data generation from DynamoDB...")

    groups = dynamo_data.get_all_groups()
    categories = dynamo_data.get_all_categories()
    single_events_raw = dynamo_data.get_single_events()
    
    single_events = []
    for event_data in single_events_raw:
        parsed = parse_single_event_data(event_data, event_data.get('id', ''), timezone_name)
        if parsed:
            single_events.append(parsed)
    
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
    
    all_events = process_events(groups, categories, single_events, ical_events_map, ALLOWED_STATES)
    
    print("Syncing events to DcTechEvents table...")
    db_utils.sync_events(all_events)

    events_json_file = os.path.join(DATA_DIR, 'events.json')
    with open(events_json_file, 'w', encoding='utf-8') as f:
        json.dump(all_events, f, indent=2, ensure_ascii=False)

    stats = calculate_stats(groups, all_events)
    stats_file = os.path.join(DATA_DIR, 'stats.yaml')
    with open(stats_file, 'w', encoding='utf-8') as f:
        yaml.dump(stats, f, sort_keys=False, allow_unicode=True)
    
    with open(UPDATED_FLAG_FILE, 'w', encoding='utf-8') as f:
        f.write(datetime.now().isoformat())
    
    print("Data generation and sync complete.")
    return True

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    generate_yaml()
    return 0

if __name__ == "__main__":
    sys.exit(main())
