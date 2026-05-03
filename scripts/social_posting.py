#!/usr/bin/env python3
import os
import json
import requests
import yaml
from datetime import datetime, timedelta
import html
import pytz
import sys

# Load configuration
CONFIG_FILE = 'config.yaml'
config = {}
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r') as f:
        config = yaml.safe_load(f)

# Define timezone from config
timezone_name = config.get('timezone', 'US/Eastern')
local_tz = pytz.timezone(timezone_name)

# Get site configuration
BASE_URL = config.get('base_url', 'https://dctech.events')

# Micro.blog API configuration
MICROPUB_ENDPOINT = "https://micro.blog/micropub"
CHAR_LIMIT = 280

# Site configurations
SITES = {
    'dctech': {
        'base_url': 'https://dctech.events',
        'data_file': '_data/dctech/all_events.json',
        'label': 'DC Tech',
        'time_offset': 0,  # No offset for dctech
    },
    'dcstem': {
        'base_url': 'https://dcstem.events',
        'data_file': '_data/dcstem/all_events.json',
        'label': 'DC STEM',
        'time_offset': 1,  # +1 hour offset for dcstem
    },
}

def is_virtual_event(event):
    """Determine if an event is virtual."""
    location = event.get('location', '').lower()
    if 'virtual' in location or 'online' in location or 'zoom' in location or 'teams' in location:
        return True
    return False

def get_events_for_date(events, target_date):
    """Filter events for a specific date."""
    target_date_str = target_date.strftime('%Y-%m-%d')
    matching_events = []
    
    for event in events:
        event_date = event.get('date')
        if not event_date:
            continue
        
        if event_date == target_date_str:
            matching_events.append(event)
            continue
        
        end_date_str = event.get('end_date')
        if end_date_str:
            try:
                event_start = datetime.strptime(event_date, '%Y-%m-%d').date()
                event_end = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                if event_start <= target_date <= event_end:
                    matching_events.append(event)
            except (ValueError, TypeError):
                pass
    
    return matching_events

def get_week_url(site_name, target_date):
    """Generate the week URL with date anchor."""
    site_config = SITES.get(site_name, SITES['dctech'])
    base_url = site_config['base_url']
    week_num = target_date.isocalendar()[1]
    year = target_date.year
    return f"{base_url}/week/{year}-W{week_num:02d}/#{target_date.strftime('%Y-%m-%d')}"

def format_event_for_post(event, site_name):
    """Format event title with site indicator and adjusted time if needed."""
    title = html.unescape(event.get('title', 'Untitled Event'))
    time_str = event.get('time', '')
    
    # Apply time offset for dcstem
    if site_name == 'dcstem' and time_str:
        try:
            hour, minute = time_str.split(':')
            hour = int(hour)
            minute = int(minute)
            # Add one hour
            hour = (hour + 1) % 24
            time_str = f'{hour:02d}:{minute:02d} (shifted)'
        except (ValueError, AttributeError):
            pass
    
    if time_str:
        return f"{title} {time_str}"
    return title

def create_post_text(events_or_dict, target_date):
    """Create post text for micro.blog under 300 characters.
    
    Supports two calling conventions:
    - create_post_text(events_list, target_date)  # old API, backward compatible
    - create_post_text(events_by_site_dict, target_date)  # new API for multi-site
    """
    
    # Check if it's a dict (new API with multi-site) or list (old API)
    if isinstance(events_or_dict, dict):
        return _create_multisite_post_text(events_or_dict, target_date)
    else:
        # Old API: single list of events
        return _create_single_site_post_text(events_or_dict, target_date)


def _create_single_site_post_text(events, target_date):
    """Create post text for a single site (backward compatible)."""
    url = get_week_url('dctech', target_date)
    prefix = "DC Tech Events today: "
    suffix = f"  {url}"
    
    overhead = len(prefix) + len(suffix)
    event_titles = [html.unescape(event.get('title', 'Untitled Event')) for event in events]
    
    if not event_titles:
        return None
    
    if len(event_titles) == 1:
        text = f"{prefix}{event_titles[0]}{suffix}"
        if len(text) <= CHAR_LIMIT:
            return text
        max_title_len = CHAR_LIMIT - overhead - 3
        truncated_title = event_titles[0][:max_title_len] + "..."
        return f"{prefix}{truncated_title}{suffix}"
    
    for num_to_show in range(len(event_titles), 0, -1):
        if num_to_show == len(event_titles):
            event_list = ", ".join(event_titles)
            text = f"{prefix}{event_list}{suffix}"
            if len(text) <= CHAR_LIMIT:
                return text
        else:
            shown_events = event_titles[:num_to_show]
            remaining = len(event_titles) - num_to_show
            event_list = ", ".join(shown_events) + f", and {remaining} more"
            text = f"{prefix}{event_list}{suffix}"
            if len(text) <= CHAR_LIMIT:
                return text
    
    return f"{prefix}{len(event_titles)} events{suffix}"


def _create_multisite_post_text(events_by_site, target_date):
    """Create post text for multiple sites combined."""
    event_titles = []
    
    for site_name in ['dctech', 'dcstem']:
        if site_name not in events_by_site:
            continue
        events = events_by_site[site_name]
        if not events:
            continue
        
        site_config = SITES[site_name]
        site_label = site_config['label']
        
        for event in events:
            formatted_title = format_event_for_post(event, site_name)
            event_titles.append(f"[{site_label}] {formatted_title}")
    
    if not event_titles:
        return None
    
    prefix = "Events today: "
    url = get_week_url('dctech', target_date)  # Use dctech URL as primary
    suffix = f"  {url}"
    
    overhead = len(prefix) + len(suffix)
    
    if len(event_titles) == 1:
        text = f"{prefix}{event_titles[0]}{suffix}"
        if len(text) <= CHAR_LIMIT:
            return text
        max_title_len = CHAR_LIMIT - overhead - 3
        truncated_title = event_titles[0][:max_title_len] + "..."
        return f"{prefix}{truncated_title}{suffix}"
    
    for num_to_show in range(len(event_titles), 0, -1):
        if num_to_show == len(event_titles):
            event_list = ", ".join(event_titles)
            text = f"{prefix}{event_list}{suffix}"
            if len(text) <= CHAR_LIMIT:
                return text
        else:
            shown_events = event_titles[:num_to_show]
            remaining = len(event_titles) - num_to_show
            event_list = ", ".join(shown_events) + f", and {remaining} more"
            text = f"{prefix}{event_list}{suffix}"
            if len(text) <= CHAR_LIMIT:
                return text
    
    return f"{prefix}{len(event_titles)} events{suffix}"

def post_to_microblog(content, token):
    """Post a note to micro.blog."""
    if not token:
        print("Error: Micro.blog token not provided")
        return False
        
    headers = {'Authorization': f'Bearer {token}'}
    data = {'h': 'entry', 'content': content}
    
    # Optional destination from environment
    mp_dest = os.environ.get('MP_DESTINATION')
    if mp_dest:
        data['mp-destination'] = mp_dest

    try:
        response = requests.post(MICROPUB_ENDPOINT, data=data, headers=headers, timeout=30)
        if response.status_code >= 500:
            print(f"Warning: micro.blog server error ({response.status_code})")
            return True
        if not response.ok:
            print(f"Error posting to micro.blog: {response.status_code} {response.reason}")
            print(f"Response body: {response.text}")
            return False
        print("Successfully posted to Micro.blog")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error posting to micro.blog: {e}")
        return False

def main():
    print("Starting daily event summary (multi-site)...")
    
    token = os.environ.get('MICROBLOG_TOKEN')
    if not token:
        print("Error: MICROBLOG_TOKEN environment variable not found")
        sys.exit(1)

    target_date = datetime.now(local_tz).date()
    print(f"Checking events for {target_date}...")
    
    # Load events from all sites
    events_by_site = {}
    for site_name, site_config in SITES.items():
        events_file = site_config['data_file']
        if not os.path.exists(events_file):
            print(f"Warning: {events_file} not found, skipping {site_name}")
            continue
        
        with open(events_file, 'r') as f:
            all_events = json.load(f)
        
        # Filter out hidden and duplicate events
        all_events = [e for e in all_events if not e.get('hidden') and not e.get('duplicate_of')]
        
        events = get_events_for_date(all_events, target_date)
        in_person_events = [e for e in events if not is_virtual_event(e)]
        
        if in_person_events:
            events_by_site[site_name] = in_person_events
            print(f"Found {len(in_person_events)} in-person events for {site_name}")
    
    if not events_by_site or not any(events_by_site.values()):
        print(f"No in-person events for {target_date}. Skipping.")
        return

    post_text = create_post_text(events_by_site, target_date)
    if not post_text:
        print("Could not generate post text")
        return

    print(f"Posting: {post_text}")
    success = post_to_microblog(post_text, token)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()

