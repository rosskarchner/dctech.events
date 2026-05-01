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
import requests
from dateutil import rrule
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
DATA_DIR = '_data'
CACHE_DIR = '_cache'
ICAL_CACHE_DIR = os.path.join(CACHE_DIR, 'ical')
GROUPS_DIR = '_groups'
CATEGORIES_DIR = '_categories'
SINGLE_EVENTS_DIR = '_single_events'
EVENT_OVERRIDES_DIR = '_event_overrides'
RECURRING_EVENTS_DIR = '_recurring_events'

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)

# Valid US state/territory abbreviations
VALID_US_STATES = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
    'DC', 'PR', 'VI', 'GU', 'MP', 'AS',
}

# Common OCR/data-entry typos for "DC"
DC_TYPO_CODES = {'DI', 'CD'}

# Max days in future for iCal events
ICAL_MAX_FUTURE_DAYS = 90

# Max days in future for recurring events
RECURRING_MAX_FUTURE_DAYS = 90

def calculate_event_hash(date, time, title, url=None):
    """Calculate MD5 hash for event identification."""
    uid_parts = [date, time, title]
    if url:
        uid_parts.append(url)
    uid_base = '-'.join(str(p) for p in uid_parts)
    return hashlib.md5(uid_base.encode('utf-8'), usedforsecurity=False).hexdigest()

def is_event_in_allowed_states(event, allowed_states):
    """Return True if the event's location is in the allowed states list.

    If allowed_states is empty, all events are allowed.  Events with no
    determinable state are assumed to be local and are allowed.
    """
    if not allowed_states:
        return True

    location = event.get('location') or ''
    if not location:
        return True  # No location info — give benefit of the doubt

    # Try structured "City, STATE" parsing via usaddress
    city, state = extract_location_info(location)
    if state is not None:
        state_upper = state.upper()
        if state_upper in VALID_US_STATES:
            return state_upper in allowed_states
        # Invalid state code — check for DC typos
        if 'DC' in allowed_states:
            city_upper = (city or '').upper()
            if city_upper == 'WASHINGTON' or state_upper in DC_TYPO_CODES:
                return True
        return False

    # Couldn't parse as a structured address — fall back to scanning for state codes
    # Collect every valid US state code that appears as a whole word in the text
    found_states = set()
    for state_code in VALID_US_STATES:
        if re.search(r'\b' + re.escape(state_code) + r'\b', location, re.IGNORECASE):
            found_states.add(state_code.upper())

    if found_states:
        # At least one state code detected; allow if any is in the allowed list
        return bool(found_states & set(allowed_states))

    # No recognizable state detected → give benefit of the doubt
    return True

def are_events_duplicates(e1, e2):
    """Return True if two events have the same title, date, and time."""
    return (e1.get('title') == e2.get('title') and
            e1.get('date') == e2.get('date') and
            e1.get('time') == e2.get('time'))

def remove_duplicates(events):
    """Deduplicate events.

    Two deduplication passes:
    1. Explicit: events with a ``duplicate_of`` field are merged into the
       referenced parent event's ``also_published_by`` list.
    2. Implicit: events with the same title+date+time are collapsed; the
       first occurrence is kept and subsequent ones are rolled into
       ``also_published_by``.
    """
    # Build guid → index map for explicit deduplication
    guid_index = {}
    for i, e in enumerate(events):
        if e.get('guid'):
            guid_index[e['guid']] = i

    result = []
    seen_indices = set()

    # Pass 1: handle explicit duplicate_of references
    explicit_children = set()
    for i, event in enumerate(events):
        dup_of = event.get('duplicate_of')
        if dup_of and dup_of in guid_index:
            parent_idx = guid_index[dup_of]
            parent = events[parent_idx]
            if 'also_published_by' not in parent:
                parent['also_published_by'] = []
            parent['also_published_by'].append({
                'group': event.get('group'),
                'group_website': event.get('group_website'),
            })
            explicit_children.add(i)

    # Pass 2: implicit deduplication by title+date+time
    for i, event in enumerate(events):
        if i in explicit_children:
            continue
        if i in seen_indices:
            continue

        duplicate_found = False
        for j in range(len(result)):
            if are_events_duplicates(result[j], event):
                if 'also_published_by' not in result[j]:
                    result[j]['also_published_by'] = []
                result[j]['also_published_by'].append({
                    'group': event.get('group'),
                    'group_website': event.get('group_website'),
                })
                duplicate_found = True
                break

        if not duplicate_found:
            result.append(event)
        seen_indices.add(i)

    return result

def get_groups():
    """Load groups from YAML files."""
    groups = []
    if not os.path.exists(GROUPS_DIR):
        return groups
    for filename in os.listdir(GROUPS_DIR):
        if filename.endswith('.yaml'):
            slug = filename[:-5]
            with open(os.path.join(GROUPS_DIR, filename), 'r') as f:
                group = yaml.safe_load(f)
                group['id'] = slug
                groups.append(group)
    return groups

def get_categories():
    """Load categories from YAML files."""
    categories = {}
    if not os.path.exists(CATEGORIES_DIR):
        return categories
    for filename in os.listdir(CATEGORIES_DIR):
        if filename.endswith('.yaml'):
            slug = filename[:-5]
            with open(os.path.join(CATEGORIES_DIR, filename), 'r') as f:
                categories[slug] = yaml.safe_load(f)
                categories[slug]['slug'] = slug
    return categories

def load_single_events():
    """Load manually submitted events from _single_events/ YAML files."""
    events = []
    if not os.path.exists(SINGLE_EVENTS_DIR):
        return events

    for filename in os.listdir(SINGLE_EVENTS_DIR):
        if not filename.endswith('.yaml'):
            continue
        filepath = os.path.join(SINGLE_EVENTS_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                event = yaml.safe_load(f)
            if not event:
                continue

            event['id'] = os.path.splitext(filename)[0]
            event['source'] = 'manual'

            # Normalize date
            if 'date' in event:
                if isinstance(event['date'], date):
                    event['date'] = event['date'].strftime('%Y-%m-%d')
                else:
                    parsed = dateparser.parse(str(event['date']), settings={
                        'TIMEZONE': timezone_name,
                        'DATE_ORDER': 'YMD',
                        'PREFER_DATES_FROM': 'future',
                    })
                    if parsed:
                        event['date'] = parsed.strftime('%Y-%m-%d')

            # Generate guid for deduplication
            event['guid'] = calculate_event_hash(
                event.get('date', ''),
                event.get('time', ''),
                event.get('title', ''),
                event.get('url'),
            )

            events.append(event)
        except Exception as e:
            print(f"Error loading single event {filename}: {e}")

    return events

def load_event_overrides():
    """Load event override data from _event_overrides/ YAML files.

    Each file is named {guid}.yaml and may contain any of:
      - title: replacement event name
      - categories: list of category slugs to use instead of the iCal categories

    Returns a dict mapping guid -> override fields dict.
    """
    overrides = {}
    if not os.path.exists(EVENT_OVERRIDES_DIR):
        return overrides

    for filename in os.listdir(EVENT_OVERRIDES_DIR):
        if not filename.endswith('.yaml'):
            continue
        guid = os.path.splitext(filename)[0]
        filepath = os.path.join(EVENT_OVERRIDES_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            if data:
                overrides[guid] = data
        except Exception as e:
            print(f"Error loading override {filepath}: {e}")

    return overrides


def load_recurring_events():
    """Load recurring events from YAML files in _recurring_events/ directory.
    
    Each file defines a recurring event with an iCal RRULE (e.g., FREQ=WEEKLY;BYDAY=TU).
    Returns a list of event dicts with 'rrule' field.
    """
    events = []
    if not os.path.exists(RECURRING_EVENTS_DIR):
        return events

    for filename in os.listdir(RECURRING_EVENTS_DIR):
        if not filename.endswith('.yaml'):
            continue
        filepath = os.path.join(RECURRING_EVENTS_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                event = yaml.safe_load(f)
            if not event:
                continue

            event['id'] = os.path.splitext(filename)[0]
            event['source'] = 'recurring'
            event['is_recurring'] = True

            # Normalize date
            if 'date' in event:
                if isinstance(event['date'], date):
                    event['date'] = event['date'].strftime('%Y-%m-%d')
                else:
                    parsed = dateparser.parse(str(event['date']), settings={
                        'TIMEZONE': timezone_name,
                        'DATE_ORDER': 'YMD',
                        'PREFER_DATES_FROM': 'future',
                    })
                    if parsed:
                        event['date'] = parsed.strftime('%Y-%m-%d')

            events.append(event)
        except Exception as e:
            print(f"Error loading recurring event {filename}: {e}")

    return events


def expand_recurring_events(recurring_events, today=None, max_days=RECURRING_MAX_FUTURE_DAYS):
    """Expand recurring events into individual instances for the next N days.
    
    Args:
        recurring_events: list of event dicts with 'rrule' field
        today: date to use as "today" (default: current date)
        max_days: number of days to project (default: 90)
    
    Returns:
        List of expanded event dicts (one per occurrence, with date filled in and 
        is_recurring flag set to True).
    """
    if today is None:
        today = datetime.now(local_tz).date()
    
    expanded = []
    max_date = today + timedelta(days=max_days)
    
    for event in recurring_events:
        rrule_str = event.get('rrule', '')
        if not rrule_str:
            continue
        
        # Parse start date
        try:
            start_date = datetime.strptime(event['date'], '%Y-%m-%d').date()
        except (KeyError, ValueError):
            continue
        
        # Skip if start date is too far in the future
        if start_date > max_date:
            continue
        
        # Parse RRULE and generate occurrences
        try:
            # Convert date to datetime for rrule
            start_dt = datetime.combine(start_date, datetime.min.time())
            start_dt = local_tz.localize(start_dt)
            
            # Parse RRULE (format: FREQ=WEEKLY;BYDAY=TU, etc.)
            rule = rrule.rrulestr(rrule_str, dtstart=start_dt)
            
            # Generate occurrences up to max_date
            for occurrence_dt in rule:
                occurrence_date = occurrence_dt.date()
                if occurrence_date > max_date:
                    break
                if occurrence_date < today:
                    continue
                
                # Create event instance
                instance = dict(event)
                instance['date'] = occurrence_date.strftime('%Y-%m-%d')
                instance['guid'] = calculate_event_hash(
                    instance['date'],
                    instance.get('time', ''),
                    instance['title'],
                    instance.get('url'),
                )
                expanded.append(instance)
        except Exception as e:
            print(f"Error expanding recurring event {event.get('id', 'unknown')}: {e}")
    
    return expanded


def process_events(groups, categories, single_events, ical_events, recurring_events, allowed_states, today=None, event_overrides=None):
    """Generate the consolidated event list from all sources.

    Args:
        groups: list of group dicts (from get_groups())
        categories: dict of category slug → category dict
        single_events: list of manually-submitted event dicts
        ical_events: dict of {group_id: [event_dicts]} from iCal cache
        recurring_events: list of recurring event dicts (with rrule field)
        allowed_states: list of state abbreviations to allow (empty = all)
        today: date to use as "today" (default: current date)
        event_overrides: dict of {guid: override_fields} from load_event_overrides()
            (default: None, meaning no overrides applied)

    Returns:
        Sorted list of deduplicated event dicts.
    """
    if today is None:
        today = datetime.now(local_tz).date()
    if event_overrides is None:
        event_overrides = {}

    max_ical_date = today + timedelta(days=ICAL_MAX_FUTURE_DAYS)

    regular_events = []
    submitted_events = []

    # 1. Process iCal events from groups
    for group in groups:
        if not group.get('active', True):
            continue

        group_id = group.get('id', '')
        suppress_urls = group.get('suppress_urls') or []
        if suppress_urls is True or suppress_urls is False:
            suppress_urls = []

        group_events = ical_events.get(group_id, [])
        for event in group_events:
            event_url = event.get('url', '')
            if event_url in suppress_urls:
                continue

            # Date filter
            try:
                event_date = datetime.strptime(event['date'], '%Y-%m-%d').date()
            except (KeyError, ValueError):
                continue
            if event_date < today or event_date > max_ical_date:
                continue

            # State filter
            if not is_event_in_allowed_states(event, allowed_states):
                continue

            processed = dict(event)
            processed['group'] = group.get('name', group_id)
            processed['group_website'] = group.get('website', '')
            processed['source'] = 'ical'
            processed['categories'] = list(group.get('categories', []))
            processed['guid'] = calculate_event_hash(
                event.get('date', ''),
                event.get('time', ''),
                event.get('title', ''),
                event.get('url'),
            )

            # Apply any override for this event's GUID
            override = event_overrides.get(processed['guid'])
            if override:
                if 'title' in override:
                    processed['title'] = override['title']
                if 'categories' in override:
                    processed['categories'] = override['categories']

            regular_events.append(processed)

    # 2. Process single/manual events (no ICAL_MAX_FUTURE_DAYS limit)
    for event in single_events:
        try:
            event_date = datetime.strptime(event['date'], '%Y-%m-%d').date()
        except (KeyError, ValueError):
            continue
        if event_date < today:
            continue

        if not is_event_in_allowed_states(event, allowed_states):
            continue

        processed = dict(event)
        processed.setdefault('source', 'manual')
        if 'guid' not in processed:
            processed['guid'] = calculate_event_hash(
                event.get('date', ''),
                event.get('time', ''),
                event.get('title', ''),
                event.get('url'),
            )
        submitted_events.append(processed)

    # 3. Expand recurring events
    recurring_expanded = expand_recurring_events(recurring_events, today=today)
    
    # 4. Combine and deduplicate (iCal takes priority over manual, recurring events included)
    combined = regular_events + recurring_expanded + submitted_events
    unique_events = remove_duplicates(combined)
    def _sort_time(event):
        t = event.get('time', '')
        if isinstance(t, dict):
            # Multi-day event with per-day times — use the time for the start date
            return t.get(event.get('date', ''), '') or ''
        return t or ''

    unique_events.sort(key=lambda x: (x.get('date', ''), _sort_time(x)))
    return unique_events

def main():
    """Load all data from files and run the event pipeline."""
    groups = get_groups()
    categories = get_categories()
    single_events = load_single_events()
    recurring_events = load_recurring_events()
    event_overrides = load_event_overrides()

    # Load iCal events from per-group cache files
    ical_events = {}
    for group in groups:
        group_id = group['id']
        cache_file = os.path.join(ICAL_CACHE_DIR, f"{group_id}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    ical_events[group_id] = json.load(f)
            except Exception as e:
                print(f"Error reading cache {cache_file}: {e}")

    unique_events = process_events(groups, categories, single_events, ical_events, recurring_events, ALLOWED_STATES, event_overrides=event_overrides)

    # Save consolidated data
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, 'all_events.json'), 'w') as f:
        json.dump(unique_events, f, indent=2)

    print(f"Generated data for {len(unique_events)} events")

if __name__ == "__main__":
    main()
