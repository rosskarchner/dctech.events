#!/usr/bin/env python3
import os
import yaml
import icalendar
import requests
import json
import pytz
import hashlib
from datetime import datetime, timedelta, timezone, date
import re
from pathlib import Path
import sys
from location_utils import extract_location_info
import recurring_ical_events
from site_utils import get_site_from_args, ensure_site_directories, get_config_file, get_groups_dir, get_cache_dir, get_categories_dir, get_data_dir

# Global constants (will be overridden per site)
CONFIG_FILE = 'config.yaml'
config = {}
timezone_name = 'US/Eastern'
local_tz = pytz.timezone(timezone_name)

# User agent for HTTP requests
USER_AGENT = 'dctech.events/1.0 (+https://dctech.events)'

# Constants - data paths (will be overridden per site)
DATA_DIR = '_data'
CACHE_DIR = '_cache'
ICAL_CACHE_DIR = os.path.join(CACHE_DIR, 'ical')
REFRESH_FLAG_FILE = os.path.join(DATA_DIR, '.refreshed')
GROUPS_DIR = '_groups'
CATEGORIES_DIR = '_categories'

# Ensure directories exist
os.makedirs(ICAL_CACHE_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

def calculate_event_hash(date, time, title, url=None):
    """
    Calculate MD5 hash for event identification.
    """
    uid_parts = [date, time, title]
    if url:
        uid_parts.append(url)

    uid_base = '-'.join(str(p) for p in uid_parts)
    uid_hash = hashlib.md5(uid_base.encode('utf-8'), usedforsecurity=False).hexdigest()
    return uid_hash

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

JSON_LD_CACHE_DIR = os.path.join(CACHE_DIR, 'json-ld')
os.makedirs(JSON_LD_CACHE_DIR, exist_ok=True)

def fetch_json_ld_title(url):
    """Fetch title from JSON-LD on the given URL (e.g. Meetup event pages)."""
    if "meetup.com" not in url:
        return None
        
    url_hash = hashlib.md5(url.encode('utf-8'), usedforsecurity=False).hexdigest()
    cache_file = os.path.join(JSON_LD_CACHE_DIR, f"{url_hash}.json")
    
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            data = json.load(f)
            return data.get('title')
            
    try:
        from bs4 import BeautifulSoup
        resp = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    ld_data = json.loads(script.string)
                    items = ld_data if isinstance(ld_data, list) else [ld_data]
                    for item in items:
                        if item.get('@type') == 'Event' and 'name' in item:
                            title = item['name']
                            with open(cache_file, 'w') as f:
                                json.dump({'title': title}, f)
                            return title
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Error fetching JSON-LD for {url}: {e}")
        pass
        
    with open(cache_file, 'w') as f:
        json.dump({'title': None}, f)
    return None

def fetch_ical_and_extract_events(url, group_id, group=None):
    """
    Fetch an iCal file and extract events.
    """
    try:
        print(f"Fetching iCal feed from {url}")
        cache_file = os.path.join(ICAL_CACHE_DIR, f"{group_id}.json")
        cache_meta_file = os.path.join(ICAL_CACHE_DIR, f"{group_id}.meta")

        headers = {'User-Agent': USER_AGENT}
        meta_data = {}

        if os.path.exists(cache_meta_file):
            with open(cache_meta_file, 'r') as f:
                try:
                    meta_data = json.load(f)
                    if not should_fetch(meta_data, group_id):
                        if os.path.exists(cache_file):
                            with open(cache_file, 'r') as f:
                                return json.load(f)
                        return None
                    if 'etag' in meta_data:
                        headers['If-None-Match'] = meta_data['etag']
                except Exception as meta_err:
                    print(f"Metadata read error: {meta_err}")
                    pass

        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 304:
            print(f"  No changes for {group_id}")
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    return json.load(f)
            return None
            
        if response.status_code != 200:
            print(f"  Error fetching {url}: {response.status_code}")
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    return json.load(f)
            return None

        calendar = icalendar.Calendar.from_ical(response.content)
        
        # Extract group name from calendar if not provided
        group_name = group.get('name') if group else group_id
        if group_name is None:
            group_name = str(calendar.get('x-wr-calname', ''))
            if not group_name:
                group_name = None # Keep it None if still empty
        
        # Determine date range for recurring events (next 6 months)
        start_date = datetime.now(timezone.utc)
        end_date = start_date + timedelta(days=180)
        
        events = []
        # Get all events including expanded recurring ones
        ical_events = recurring_ical_events.of(calendar).between(start_date, end_date)
        
        for event in ical_events:
            dtstart = event.get('dtstart').dt
            if isinstance(dtstart, datetime):
                dt_local = dtstart.astimezone(local_tz)
                date_str = dt_local.strftime('%Y-%m-%d')
                time_str = dt_local.strftime('%H:%M')
                # Treat midnight (00:00) as all-day — many calendars use a midnight
                # datetime to represent all-day events instead of a DATE-only value.
                if time_str == '00:00':
                    time_str = ''
            else:
                date_str = dtstart.strftime('%Y-%m-%d')
                time_str = ""
                
            dtend = event.get('dtend')
            end_date_str = ""
            end_time_str = ""
            if dtend:
                dtend = dtend.dt
                if isinstance(dtend, datetime):
                    dt_end_local = dtend.astimezone(local_tz)
                    end_date_str = dt_end_local.strftime('%Y-%m-%d')
                    end_time_str = dt_end_local.strftime('%H:%M')
                else:
                    end_date_str = dtend.strftime('%Y-%m-%d')

            title = str(event.get('summary', 'Untitled Event'))
            url_field = event.get('url')
            if url_field:
                event_url = str(url_field)
            else:
                # Fallback to description search for URL
                desc = str(event.get('description', ''))
                url_match = re.search(r'https?://[^\s<>"]+|www\.[^\s<>"]+', desc)
                event_url = url_match.group(0) if url_match else group.get('website', '')

            if event_url:
                canonical_title = fetch_json_ld_title(event_url)
                if canonical_title:
                    title = canonical_title

            event_data = {
                'title': title,
                'date': date_str,
                'time': time_str,
                'end_date': end_date_str,
                'end_time': end_time_str,
                'url': event_url,
                'location': str(event.get('location', '')),
                'description': str(event.get('description', '')),
                'group': group_name,
                'group_id': group_id,
            }

            event_categories = set(group.get('categories', []) if group else [])
            ical_categories = event.get('categories')
            if ical_categories:
                if not isinstance(ical_categories, list):
                    ical_categories = [ical_categories]
                for cat in ical_categories:
                    if hasattr(cat, 'to_ical'):
                        val = cat.to_ical().decode('utf-8')
                        for c in val.split(','):
                            c_clean = c.strip()
                            if c_clean:
                                event_categories.add(c_clean)
                    elif isinstance(cat, str):
                        for c in cat.split(','):
                            c_clean = c.strip()
                            if c_clean:
                                event_categories.add(c_clean)
            
            event_data['categories'] = list(event_categories)
            events.append(event_data)

        # Update cache
        with open(cache_file, 'w') as f:
            json.dump(events, f)
            
        meta_data = {
            'last_fetch': datetime.now(timezone.utc).isoformat(),
            'etag': response.headers.get('ETag'),
            'last_modified': response.headers.get('Last-Modified')
        }
        with open(cache_meta_file, 'w') as f:
            json.dump(meta_data, f)
            
        return events

    except Exception as e:
        print(f"  Error processing {group_id}: {e}")
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                return json.load(f)
        return None

def get_groups():
    """Load groups from YAML files in _groups directory."""
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

def refresh_calendars(site=None):
    """
    Fetch all iCal files from groups for a specific site.
    If site is None, uses globals (for backward compatibility).
    """
    if site is not None:
        # Set up site-specific paths
        global CONFIG_FILE, config, timezone_name, local_tz
        global DATA_DIR, CACHE_DIR, ICAL_CACHE_DIR, REFRESH_FLAG_FILE, GROUPS_DIR, CATEGORIES_DIR
        
        CONFIG_FILE = get_config_file(site)
        config = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = yaml.safe_load(f)
        
        # Initialize timezone from config
        timezone_name = config.get('timezone', 'US/Eastern')
        local_tz = pytz.timezone(timezone_name)
        
        # Update path constants for this site
        DATA_DIR = get_data_dir(site)
        CACHE_DIR = get_cache_dir(site)
        ICAL_CACHE_DIR = os.path.join(CACHE_DIR, 'ical')
        REFRESH_FLAG_FILE = os.path.join(DATA_DIR, '.refreshed')
        GROUPS_DIR = get_groups_dir(site)
        CATEGORIES_DIR = get_categories_dir(site)
        
        # Ensure directories exist
        os.makedirs(ICAL_CACHE_DIR, exist_ok=True)
        os.makedirs(DATA_DIR, exist_ok=True)
    
    print("Refreshing calendars...")
    groups = get_groups()
    updated = False

    for group in groups:
        if not group.get('active', True):
            continue
            
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

    # Generate categories.json for the edit site
    generate_categories_json()

    return updated

def generate_categories_json():
    """Generate a JSON file with all categories for the edit site."""
    categories = {}
    if os.path.exists(CATEGORIES_DIR):
        for filename in os.listdir(CATEGORIES_DIR):
            if filename.endswith('.yaml'):
                slug = filename[:-5]
                with open(os.path.join(CATEGORIES_DIR, filename), 'r') as f:
                    cat = yaml.safe_load(f)
                    categories[slug] = {
                        'slug': slug,
                        'name': cat.get('name', slug),
                        'description': cat.get('description', '')
                    }
    
    os.makedirs('static', exist_ok=True)
    with open('static/categories.json', 'w') as f:
        json.dump(categories, f, indent=2)
    print(f"Generated static/categories.json with {len(categories)} categories")

def main():
    sites = get_site_from_args('dctech')
    
    for site in sites:
        print(f"\nProcessing site: {site}")
        ensure_site_directories(site)
        refresh_calendars(site)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
