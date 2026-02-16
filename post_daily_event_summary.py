#!/usr/bin/env python3
"""
Post daily summary of newly added events to micro.blog.

This script:
1. Checks for new events added today by reading DynamoDB
2. Posts a summary to micro.blog if there are new events
3. Format: "X new events added on [Month Day, Year]"

Environment Variables Required:
- MB_TOKEN: App token from micro.blog (Account → App tokens)
- MICROBLOG_DESTINATION: (Optional) Custom domain URL for multi-blog accounts
                         Defaults to https://updates.dctech.events/

Usage:
    export MB_TOKEN="your-token-here"
    # MICROBLOG_DESTINATION is optional - defaults to https://updates.dctech.events/
    python post_daily_event_summary.py
    python post_daily_event_summary.py --dry-run  # Test without posting
"""

import os
import sys
import yaml
import argparse
from datetime import datetime, timedelta, timezone
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
SITE_NAME = config.get('site_name', 'DC Tech Events')
BASE_URL = config.get('base_url', 'https://dctech.events')

# Micro.blog API configuration
MB_TOKEN = os.environ.get('MB_TOKEN')
# Default to updates.dctech.events if not specified
MICROBLOG_DESTINATION = os.environ.get('MICROBLOG_DESTINATION', 'https://updates.dctech.events/')
MICROPUB_ENDPOINT = "https://micro.blog/micropub"

def get_todays_new_events(target_date=None):
    """
    Get events that were first seen on the target date.
    """
    if target_date is None:
        # Get current date in local timezone
        target_date = datetime.now(local_tz).date()
    
    # Fetch 100 recent events (should be enough for a day)
    recent_events = db_utils.get_recently_added(limit=100)
    new_events = []
    
    for event in recent_events:
        first_seen = event.get('createdAt')
        if not first_seen:
            continue
        
        try:
            # Parse the UTC timestamp
            first_seen_dt = datetime.fromisoformat(first_seen.replace('Z', '+00:00'))
            # Convert to local timezone
            first_seen_local = first_seen_dt.astimezone(local_tz)
            # Get just the date
            first_seen_date = first_seen_local.date()
            
            if first_seen_date == target_date:
                new_events.append(event)
        except (ValueError, AttributeError) as e:
            continue
    
    return new_events


def generate_summary_content(count, target_date):
    """
    Generate summary content with link to just-added page.
    """
    # Format the anchor (e.g., "2-5-2026" for Feb 5, 2026)
    anchor = f"{target_date.month}-{target_date.day}-{target_date.year}"
    
    # Build the URL with anchor
    url = f"{BASE_URL}/just-added/#{anchor}"
    
    # Pluralize "event" if needed
    event_word = 'event' if count == 1 else 'events'
    
    # Simple text with link
    return f"{count} new {event_word} added today: {url}"


def post_to_microblog(content, token, destination=None, dry_run=False):
    """
    Post content to micro.blog using form-encoded Micropub.
    """
    if dry_run:
        print("\n=== DRY RUN - Would post to micro.blog ===")
        print(f"Endpoint: {MICROPUB_ENDPOINT}")
        print(f"Content:\n{content}")
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
        response.raise_for_status()

        post_url = response.headers.get('Location', 'posted successfully')
        print(f"Successfully posted to micro.blog: {post_url}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"Error posting to micro.blog: {e}")
        return False


def main():
    """Main entry point. TEMPORARILY DISABLED."""
    print("Daily event summary posting is temporarily disabled.")
    return 0
    parser = argparse.ArgumentParser(
        description='Post daily summary of new events to micro.blog'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be posted without actually posting'
    )
    parser.add_argument(
        '--date',
        type=str,
        help='Check for events added on specific date (YYYY-MM-DD). Default: today'
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
    
    print(f"Checking for events added on {target_date.strftime('%Y-%m-%d')}...")
    
    # Get events added today
    new_events = get_todays_new_events(target_date)
    
    if not new_events:
        print(f"No new events found for {target_date.strftime('%B %-d, %Y')}")
        print("Nothing to post.")
        return 0
    
    print(f"Found {len(new_events)} new events")
    
    # Generate content with link to just-added page
    content = generate_summary_content(len(new_events), target_date)
    
    print(f"Post content: {content}")
    
    # Post to micro.blog (untitled post)
    success = post_to_microblog(
        content=content,
        token=MB_TOKEN,
        destination=MICROBLOG_DESTINATION,
        dry_run=args.dry_run
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())