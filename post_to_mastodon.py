#!/usr/bin/env python3
"""
Post daily event summary to Mastodon using ActivityPub API.

This script posts a summary of tech events happening today to a Mastodon account.
It only posts if there are events scheduled for the current day.

Mastodon API Details:
- Uses the Mastodon REST API (compatible with ActivityPub/W3C standard)
- Authentication via OAuth2 access token
- Posts are called "statuses" in ActivityPub terminology
- Maximum character limit: 500 characters (default, can vary by instance)
- Supports rich text formatting using Markdown-like syntax
- Uses HTTPS for all API calls

ActivityPub Standards in Use:
- ActivityPub (W3C Recommendation): Decentralized social networking protocol
- OAuth 2.0: For authentication and authorization
- ActivityStreams 2.0: JSON-based format for social data
- HTTP Signatures: For server-to-server authentication (handled by Mastodon)

Environment Variables Required:
- MASTODON_ACCESS_TOKEN: OAuth2 access token for posting
- MASTODON_INSTANCE_URL: Base URL of Mastodon instance (e.g., https://mastodon.social)

Usage:
    export MASTODON_ACCESS_TOKEN="your-token-here"
    export MASTODON_INSTANCE_URL="https://mastodon.social"
    python post_to_mastodon.py
    python post_to_mastodon.py --dry-run  # Test without posting
    python post_to_mastodon.py --date 2026-01-15  # Post for specific date
"""

import os
import sys
import yaml
import argparse
from datetime import datetime, date
import requests
import pytz
from pathlib import Path

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

# Data paths
DATA_DIR = '_data'
UPCOMING_FILE = os.path.join(DATA_DIR, 'upcoming.yaml')

# Mastodon API configuration
MASTODON_ACCESS_TOKEN = os.environ.get('MASTODON_ACCESS_TOKEN')
MASTODON_INSTANCE_URL = os.environ.get('MASTODON_INSTANCE_URL')

# Character limit for Mastodon (conservative estimate)
MASTODON_CHAR_LIMIT = 500


def load_events():
    """Load events from upcoming.yaml file."""
    if not os.path.exists(UPCOMING_FILE):
        print(f"Warning: {UPCOMING_FILE} not found. Run 'make generate-month-data' first.")
        return []
    
    with open(UPCOMING_FILE, 'r', encoding='utf-8') as f:
        events = yaml.safe_load(f)
        return events if events else []


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


def format_event_line(event, max_length=100):
    """
    Format a single event as a line of text with clickable link.
    
    For Mastodon, we include the URL after the title in plain text,
    and Mastodon will automatically make it clickable.
    
    Args:
        event: Event dictionary
        max_length: Maximum length for the event line
    
    Returns:
        Formatted string for the event
    """
    title = event.get('title', 'Untitled Event')
    url = event.get('url', '')
    
    # Format event line without time, but with URL
    if url:
        event_line = f"• {title} {url}"
    else:
        event_line = f"• {title}"
    
    # Truncate if too long
    if len(event_line) > max_length:
        # Try to preserve the URL if possible
        if url:
            # Calculate space needed for URL and ellipsis
            url_with_space = f" {url}"
            available_for_title = max_length - len(url_with_space) - len("• ") - 3  # 3 for "..."
            if available_for_title > 10:  # Minimum reasonable title length
                truncated_title = title[:available_for_title] + "..."
                event_line = f"• {truncated_title}{url_with_space}"
            else:
                # URL too long, just truncate everything
                event_line = event_line[:max_length-3] + "..."
        else:
            event_line = event_line[:max_length-3] + "..."
    
    return event_line


def create_mastodon_post(events, target_date, base_url):
    """
    Create a Mastodon post text for the events.
    
    Args:
        events: List of events
        target_date: Date for the events
        base_url: Base URL of the website
    
    Returns:
        Post text string
    """
    # Format date
    date_str = target_date.strftime('%A, %B %-d, %Y')
    
    # Start building the post
    intro = f"📅 Tech events happening today ({target_date.strftime('%B %-d')}):\n\n"
    
    # Calculate how much space we have for events
    url_line = f"\n\nMore info: {base_url}"
    overhead = len(intro) + len(url_line)
    available_chars = MASTODON_CHAR_LIMIT - overhead - 50  # 50 char buffer
    
    # Add events
    event_lines = []
    current_length = 0
    events_shown = 0
    
    for event in events[:10]:  # Limit to first 10 events
        event_line = format_event_line(event)
        line_length = len(event_line) + 1  # +1 for newline
        
        if current_length + line_length > available_chars:
            remaining = len(events) - events_shown
            if remaining > 0:
                event_lines.append(f"...and {remaining} more")
            break
        
        event_lines.append(event_line)
        current_length += line_length
        events_shown += 1
    
    # Combine all parts
    post_text = intro + "\n".join(event_lines) + url_line
    
    return post_text


def post_to_mastodon(status_text, dry_run=False):
    """
    Post a status to Mastodon using the REST API.
    
    Args:
        status_text: Text content to post
        dry_run: If True, print what would be posted without actually posting
    
    Returns:
        True if successful, False otherwise
    """
    if dry_run:
        instance = MASTODON_INSTANCE_URL or "https://mastodon.social"
        print("\n=== DRY RUN - Would post to Mastodon ===")
        print(f"Instance: {instance}")
        print(f"Post length: {len(status_text)} characters")
        print(f"\n{status_text}")
        print("\n=== End of dry run ===\n")
        return True
    
    if not MASTODON_ACCESS_TOKEN or not MASTODON_INSTANCE_URL:
        print("Error: MASTODON_ACCESS_TOKEN and MASTODON_INSTANCE_URL environment variables must be set")
        return False
    
    # Mastodon API endpoint for posting statuses
    api_url = f"{MASTODON_INSTANCE_URL}/api/v1/statuses"
    
    # Prepare headers with OAuth2 bearer token
    headers = {
        'Authorization': f'Bearer {MASTODON_ACCESS_TOKEN}',
        'Content-Type': 'application/json',
    }
    
    # Prepare post data (ActivityStreams format)
    data = {
        'status': status_text,
        'visibility': 'public',  # Can be: public, unlisted, private, direct
    }
    
    try:
        # Make POST request to Mastodon API
        response = requests.post(api_url, json=data, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Parse response (ActivityStreams object)
        result = response.json()
        post_url = result.get('url', 'posted successfully')
        
        print(f"✓ Successfully posted to Mastodon: {post_url}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error posting to Mastodon: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return False


def main():
    """Main function to post daily event summary to Mastodon."""
    parser = argparse.ArgumentParser(
        description='Post daily event summary to Mastodon',
        epilog='Requires MASTODON_ACCESS_TOKEN and MASTODON_INSTANCE_URL environment variables'
    )
    parser.add_argument(
        '--date',
        type=str,
        help='Date to post events for (YYYY-MM-DD). Defaults to today.'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be posted without actually posting'
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
        # Use current date in configured timezone
        target_date = datetime.now(local_tz).date()
    
    print(f"Checking events for {target_date.strftime('%A, %B %-d, %Y')}...")
    
    # Load all events
    all_events = load_events()
    if not all_events:
        print("No events data available.")
        return 1
    
    # Filter events for target date
    events = get_events_for_date(all_events, target_date)
    
    if not events:
        print(f"✓ No events scheduled for {target_date}. Nothing to post.")
        # Find the next upcoming event to provide context
        future_events = [e for e in all_events if e.get('date') and e.get('date') >= target_date.strftime('%Y-%m-%d')]
        if future_events:
            next_event = future_events[0]
            print(f"ℹ️  Next event: {next_event.get('title', 'Unknown')} on {next_event.get('date')}")
        return 0
    
    print(f"Found {len(events)} event(s) for {target_date}")
    
    # Create post text
    post_text = create_mastodon_post(events, target_date, BASE_URL)
    
    # Post to Mastodon
    success = post_to_mastodon(post_text, dry_run=args.dry_run)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
