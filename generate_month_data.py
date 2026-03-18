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

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)

def calculate_event_hash(date, time, title, url=None):
    """Calculate MD5 hash for event identification."""
    uid_parts = [date, time, title]
    if url:
        uid_parts.append(url)
    uid_base = '-'.join(str(p) for p in uid_parts)
    return hashlib.md5(uid_base.encode('utf-8'), usedforsecurity=False).hexdigest()

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

def process_events():
    """Generate the consolidated event data from all sources."""
    groups = get_groups()
    categories = get_categories()
    
    regular_events = []
    submitted_events = []
    today = datetime.now(local_tz).date()
    max_future_date = today + timedelta(days=120)
    
    # Track events seen in current run to handle disappearances
    current_run_guids = set()

    # 1. Process regular scraped groups
    for group in groups:
        if not group.get('active', True):
            continue
            
        group_id = group['id']
        cache_file = os.path.join(ICAL_CACHE_DIR, f"{group_id}.json")
        
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                try:
                    events = json.load(f)
                    for event in events:
                        event_hash = calculate_event_hash(
                            event.get('date', ''),
                            event.get('time', ''),
                            event.get('title', ''),
                            event.get('url')
                        )
                        
                        event['guid'] = event_hash
                        current_run_guids.add(event_hash)
                        
                        # Filter by date
                        try:
                            event_date = datetime.strptime(event['date'], '%Y-%m-%d').date()
                            if today <= event_date <= max_future_date:
                                regular_events.append(event)
                        except Exception as parse_err:
                            print(f"Date parse error (regular): {parse_err}")
                            continue
                except Exception as e:
                    print(f"Error processing {group_id}: {e}")

    # 2. Process submitted events
    submitted_cache = os.path.join(ICAL_CACHE_DIR, "submitted-events.json")
    if os.path.exists(submitted_cache):
         with open(submitted_cache, 'r') as f:
            try:
                events = json.load(f)
                for event in events:
                    guid = event.get('uid') or calculate_event_hash(
                        event.get('date', ''),
                        event.get('time', ''),
                        event.get('title', ''),
                        event.get('url')
                    )
                    event['guid'] = guid
                    current_run_guids.add(guid)
                    # Date filter
                    try:
                        event_date = datetime.strptime(event['date'], '%Y-%m-%d').date()
                        if today <= event_date <= max_future_date:
                            submitted_events.append(event)
                    except Exception as parse_err:
                        print(f"Date parse error (submitted): {parse_err}")
                        continue
            except Exception as e:
                print(f"Error processing submitted events: {e}")

    # 3. Same-day stability: Keep events from previous run if they are for today
    previous_data = []
    previous_data_file = os.path.join(DATA_DIR, 'all_events.json')
    if os.path.exists(previous_data_file):
        with open(previous_data_file, 'r') as f:
            try:
                prev_events = json.load(f)
                for prev_event in prev_events:
                    guid = prev_event.get('guid')
                    if guid not in current_run_guids:
                        try:
                            event_date = datetime.strptime(prev_event['date'], '%Y-%m-%d').date()
                            if event_date == today:
                                previous_data.append(prev_event)
                        except Exception as parse_err:
                            print(f"Date parse error (prev): {parse_err}")
                            pass
            except Exception as read_err:
                print(f"Error reading prev data: {read_err}")
                pass

    # Deduplicate: Regular events > Submitted events > Previous stability events
    seen_guids = set()
    unique_events = []
    
    for e in regular_events:
        if e['guid'] not in seen_guids:
            unique_events.append(e)
            seen_guids.add(e['guid'])
            
    for e in submitted_events:
        if e['guid'] not in seen_guids:
            unique_events.append(e)
            seen_guids.add(e['guid'])
            
    for e in previous_data:
        if e['guid'] not in seen_guids:
            unique_events.append(e)
            seen_guids.add(e['guid'])
            
    unique_events.sort(key=lambda x: (x.get('date', ''), x.get('time', '')))
    
    # Save consolidated data
    with open(os.path.join(DATA_DIR, 'all_events.json'), 'w') as f:
        json.dump(unique_events, f, indent=2)
        
    print(f"Generated data for {len(unique_events)} events")

def main():
    process_events()

if __name__ == "__main__":
    main()
