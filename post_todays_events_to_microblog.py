#!/usr/bin/env python3
"""
Post today's events to micro.blog.

This script posts a text-only summary of events happening today to micro.blog.
Posts are under 300 characters and use one of these formats (in order of preference):

1. "DC Tech Events today: Event1, Event2, and Event3  https://dctech.events/week/2026-W06/#2026-02-06"
2. "DC Tech Events today: Event1, Event2, and 3 more  https://dctech.events/week/2026-W06/#2026-02-06"

Environment Variables Required:
- MB_TOKEN: App token from micro.blog (Account → App tokens)
- MICROBLOG_DESTINATION: (Optional) Custom domain URL for multi-blog accounts
                         Defaults to https://updates.dctech.events/

Usage:
    export MB_TOKEN="your-token-here"
    # MICROBLOG_DESTINATION is optional - defaults to https://updates.dctech.events/
    python post_todays_events_to_microblog.py
    python post_todays_events_to_microblog.py --dry-run  # Test without posting
    python post_todays_events_to_microblog.py --date 2026-02-06  # Post for specific date
"""

import os
import sys
import yaml
import argparse
from datetime import datetime
import requests
import pytz
import db_utils

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

# Data paths
DATA_DIR = '_data'
UPCOMING_FILE = os.path.join(DATA_DIR, 'upcoming.yaml')

# Micro.blog API configuration
MB_TOKEN = os.environ.get('MB_TOKEN')
# Default to updates.dctech.events if not specified
MICROBLOG_DESTINATION = os.environ.get('MICROBLOG_DESTINATION', 'https://updates.dctech.events/')
MICROPUB_ENDPOINT = "https://micro.blog/micropub"

# Character limit for micro.blog posts
CHAR_LIMIT = 300


def load_events():
    """Load events from DynamoDB."""
    events = db_utils.get_future_events()
    return events if events else []


def is_virtual_event(event):
    """
    Determine if an event is virtual based on its location_type field.
    
    Args:
        event: Event dictionary
    
    Returns:
        True if event is virtual, False otherwise
    """
    return event.get('location_type') == 'virtual'


def get_events_for_date(events, target_date):
    """
    Filter events for a specific date.
    
    Args:
        events: List of all events
        target_date: Date to filter for (date object)
    
    Returns:
        List of events happening on target_date
    """
    target_date_str = target_date.strftime('%Y-%m-%d')
    matching_events = []
    
    for event in events:
        event_date = event.get('date')
        if not event_date:
            continue
        
        # Check if event is on target date
        if event_date == target_date_str:
            matching_events.append(event)
            continue
        
        # Check if it's a multi-day event that includes target date
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


def get_week_url(target_date):
    """
    Generate the week URL with date anchor for a given date.
    
    Args:
        target_date: Date object
    
    Returns:
        URL string like "https://dctech.events/week/2026-W06/#2026-02-06"
    """
    week = target_date.isocalendar()
    return f"{BASE_URL}/week/{week.year}-W{week.week:02d}/#{target_date.strftime('%Y-%m-%d')}"


def create_post_text(events, target_date):
    """
    Create post text for micro.blog under 300 characters.
    
    Uses format preference:
    1. "DC Tech Events today: Event1, Event2, and Event3  URL"
    2. "DC Tech Events today: Event1, Event2, and 3 more  URL"
    
    Args:
        events: List of events
        target_date: Date for the events
    
    Returns:
        Post text string under 300 characters
    """
    url = get_week_url(target_date)
    prefix = "DC Tech Events today: "
    suffix = f"  {url}"
    
    # Calculate space available for event titles
    overhead = len(prefix) + len(suffix)
    available_chars = CHAR_LIMIT - overhead
    
    # Build list of event titles
    event_titles = [event.get('title', 'Untitled Event') for event in events]
    
    # Try to fit as many events as possible in full list format
    # Format: "Event1, Event2, and Event3"
    if len(event_titles) == 0:
        return None
    
    if len(event_titles) == 1:
        # Single event: "DC Tech Events today: Event1  URL"
        text = f"{prefix}{event_titles[0]}{suffix}"
        if len(text) <= CHAR_LIMIT:
            return text
        # Truncate title if needed
        max_title_len = CHAR_LIMIT - overhead - 3  # 3 for "..."
        truncated_title = event_titles[0][:max_title_len] + "..."
        return f"{prefix}{truncated_title}{suffix}"
    
    # Try full list format: "Event1, Event2, and Event3"
    # Start with all events
    for num_to_show in range(len(event_titles), 0, -1):
        if num_to_show == len(event_titles):
            # Full list
            event_list = ", ".join(event_titles)
            text = f"{prefix}{event_list}{suffix}"
            if len(text) <= CHAR_LIMIT:
                return text
        else:
            # "and N more" format: "Event1, Event2, and 3 more"
            shown_events = event_titles[:num_to_show]
            remaining = len(event_titles) - num_to_show
            event_list = ", ".join(shown_events) + f", and {remaining} more"
            text = f"{prefix}{event_list}{suffix}"
            if len(text) <= CHAR_LIMIT:
                return text
    
    # If we still can't fit, try with just first event and "and N more"
    if len(event_titles) > 1:
        remaining = len(event_titles) - 1
        text = f"{prefix}{event_titles[0]}, and {remaining} more{suffix}"
        if len(text) <= CHAR_LIMIT:
            return text
        # Truncate first title
        max_title_len = CHAR_LIMIT - len(prefix) - len(f", and {remaining} more{suffix}") - 3
        if max_title_len > 10:
            truncated_title = event_titles[0][:max_title_len] + "..."
            return f"{prefix}{truncated_title}, and {remaining} more{suffix}"
    
    # Last resort: just show count
    return f"{prefix}{len(event_titles)} events{suffix}"


def post_to_microblog(content, token, destination=None, dry_run=False):
    """
    Post text-only content to micro.blog using Micropub.

    Args:
        content: Post text content (no title)
        token: Micro.blog app token
        destination: Optional destination URL
        dry_run: If True, print what would be posted

    Returns:
        True if successful, False otherwise
    """
    if dry_run:
        print("\n=== DRY RUN - Would post to micro.blog ===")
        print(f"Endpoint: {MICROPUB_ENDPOINT}")
        print(f"Content ({len(content)} chars):\n{content}")
        if destination:
            print(f"Destination: {destination}")
        print("=== End of dry run ===\n")
        return True

    if not token:
        print("Error: MB_TOKEN environment variable must be set")
        return False

    headers = {
        'Authorization': f'Bearer {token}',
    }

    # Form-encoded payload for text-only post (no name/title)
    data = {
        'h': 'entry',
        'content': content,
    }

    if destination:
        data['mp-destination'] = destination

    try:
        response = requests.post(
            MICROPUB_ENDPOINT,
            data=data,
            headers=headers,
            timeout=30
        )
        
        # Check for server errors (5xx) - treat as non-fatal per repo memory
        if response.status_code >= 500:
            print(f"Warning: micro.blog server error ({response.status_code}), but treating as non-fatal")
            print(f"Response: {response.text}")
            return True  # Return True to not fail workflow
        
        response.raise_for_status()

        post_url = response.headers.get('Location', 'posted successfully')
        print(f"Successfully posted to micro.blog: {post_url}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"Error posting to micro.blog: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Post today's events to micro.blog",
        epilog='Requires MB_TOKEN environment variable'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be posted without actually posting'
    )
    parser.add_argument(
        '--date',
        type=str,
        help='Post events for specific date (YYYY-MM-DD). Default: today'
    )
    
    args = parser.parse_args()
    
    # Determine target date
    if args.date:
        try:
            target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        except ValueError:
            print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD")
            return 1
    else:
        target_date = datetime.now(local_tz).date()
    
    print(f"Checking events for {target_date.strftime('%A, %B %-d, %Y')}...")
    
    # Load all events
    all_events = load_events()
    if not all_events:
        print("No events data available.")
        return 1
    
    # Filter events for target date
    events = get_events_for_date(all_events, target_date)
    
    # Filter out virtual events (only post in-person events)
    in_person_events = [event for event in events if not is_virtual_event(event)]
    
    if not in_person_events:
        virtual_count = len(events)
        if virtual_count > 0:
            print(f"Found {virtual_count} event(s) for {target_date}, but all are virtual. Nothing to post.")
        else:
            print(f"No events found for {target_date}. Nothing to post.")
        return 0
    
    virtual_count = len(events) - len(in_person_events)
    if virtual_count > 0:
        print(f"Found {len(events)} event(s) for {target_date} ({virtual_count} virtual, {len(in_person_events)} in-person)")
    else:
        print(f"Found {len(in_person_events)} in-person event(s) for {target_date}")
    
    # Create post text
    post_text = create_post_text(in_person_events, target_date)
    
    if not post_text:
        print("Could not create post text. No events to post.")
        return 0
    
    print(f"Post text ({len(post_text)} characters): {post_text}")
    
    # Post to micro.blog
    success = post_to_microblog(
        content=post_text,
        token=MB_TOKEN,
        destination=MICROBLOG_DESTINATION,
        dry_run=args.dry_run
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
