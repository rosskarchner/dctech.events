#!/usr/bin/env python3
"""
Post weekly event preview to Mastodon using ActivityPub API.

This script posts a preview of tech events happening in the upcoming week to a Mastodon account.
Designed to run on Thursday afternoons to preview the following week (Monday-Sunday).

Mastodon API Details:
- Uses the Mastodon REST API (compatible with ActivityPub/W3C standard)
- Authentication via OAuth2 access token
- Posts are called "statuses" in ActivityPub terminology
- Maximum character limit: 500 characters (default, can vary by instance)
- Supports rich text formatting using Markdown-like syntax
- Uses HTTPS for all API calls

Environment Variables Required:
- MASTODON_ACCESS_TOKEN: OAuth2 access token for posting
- MASTODON_INSTANCE_URL: Base URL of Mastodon instance (e.g., https://mastodon.social)

Usage:
    export MASTODON_ACCESS_TOKEN="your-token-here"
    export MASTODON_INSTANCE_URL="https://mastodon.social"
    python post_weekly_preview_to_mastodon.py
    python post_weekly_preview_to_mastodon.py --dry-run  # Test without posting
    python post_weekly_preview_to_mastodon.py --start-date 2026-01-13  # Custom week start
"""

import os
import sys
import yaml
import argparse
from datetime import datetime, date, timedelta
import requests
import pytz
from pathlib import Path
from collections import defaultdict

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


def get_next_monday(reference_date=None):
    """
    Get the date of the next Monday from the reference date.

    Args:
        reference_date: Date to calculate from (defaults to today)

    Returns:
        Date object for the next Monday
    """
    if reference_date is None:
        reference_date = datetime.now(local_tz).date()

    # Calculate days until next Monday (0 = Monday, 6 = Sunday)
    days_ahead = 0 - reference_date.weekday()
    if days_ahead <= 0:  # If today is Monday or later in the week
        days_ahead += 7

    return reference_date + timedelta(days=days_ahead)


def get_events_for_week(events, start_date):
    """
    Filter events for a specific week (7 days starting from start_date).

    Args:
        events: List of all events
        start_date: Start date of the week (date object)

    Returns:
        Dictionary mapping date strings to list of events
    """
    end_date = start_date + timedelta(days=6)
    events_by_date = defaultdict(list)

    for event in events:
        event_date_str = event.get('date')
        if not event_date_str:
            continue

        try:
            event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()

            # Check if event is within the week
            if start_date <= event_date <= end_date:
                events_by_date[event_date_str].append(event)
                continue

            # Check if it's a multi-day event that overlaps with the week
            end_date_str = event.get('end_date')
            if end_date_str:
                event_end = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                # If event overlaps with our week at all
                if event_date <= end_date and event_end >= start_date:
                    # Add to each day it occurs during the week
                    current = max(event_date, start_date)
                    last = min(event_end, end_date)
                    while current <= last:
                        events_by_date[current.strftime('%Y-%m-%d')].append(event)
                        current += timedelta(days=1)
        except (ValueError, TypeError):
            pass

    return dict(events_by_date)


def create_weekly_preview_post(events_by_date, start_date, base_url):
    """
    Create a Mastodon post text for the weekly preview.

    Args:
        events_by_date: Dictionary mapping date strings to list of events
        start_date: Start date of the week
        base_url: Base URL of the website

    Returns:
        Post text string
    """
    end_date = start_date + timedelta(days=6)

    # Count total events
    total_events = sum(len(events) for events in events_by_date.values())

    if total_events == 0:
        # No events message
        intro = f"📅 Week of {start_date.strftime('%b %-d')}: No tech events scheduled yet.\n\n"
        return intro + f"Check {base_url} for updates!"

    # Build intro
    date_range = f"{start_date.strftime('%b %-d')}-{end_date.strftime('%-d')}"
    intro = f"📅 Preview: {total_events} tech event{'s' if total_events != 1 else ''} next week ({date_range}):\n\n"

    # Calculate available space
    url_line = f"\n\n{base_url}"
    overhead = len(intro) + len(url_line)
    available_chars = MASTODON_CHAR_LIMIT - overhead - 50  # 50 char buffer

    # Build event list grouped by day
    event_lines = []
    current_length = 0
    total_shown = 0

    # Sort dates
    sorted_dates = sorted(events_by_date.keys())

    for date_str in sorted_dates:
        events = events_by_date[date_str]
        event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        day_name = event_date.strftime('%a')  # Mon, Tue, etc.

        # Day header
        day_header = f"{day_name} ({len(events)}):\n"

        # Check if we have space for at least the header
        if current_length + len(day_header) > available_chars:
            remaining = total_events - total_shown
            if remaining > 0:
                event_lines.append(f"\n...and {remaining} more")
            break

        event_lines.append(day_header)
        current_length += len(day_header)

        # Add events for this day
        for event in events[:3]:  # Max 3 events per day
            title = event.get('title', 'Untitled Event')
            url = event.get('url', '')

            # Format: • Title URL
            if url:
                event_line = f"• {title} {url}\n"
            else:
                event_line = f"• {title}\n"

            # Truncate if too long
            max_event_length = 120
            if len(event_line) > max_event_length:
                if url:
                    # Try to preserve URL
                    available_for_title = max_event_length - len(f" {url}\n") - len("• ") - 3
                    if available_for_title > 10:
                        truncated_title = title[:available_for_title] + "..."
                        event_line = f"• {truncated_title} {url}\n"
                    else:
                        event_line = event_line[:max_event_length-3] + "...\n"
                else:
                    event_line = event_line[:max_event_length-3] + "...\n"

            # Check if we have space
            if current_length + len(event_line) > available_chars:
                remaining = total_events - total_shown
                if remaining > 0:
                    event_lines.append(f"\n...and {remaining} more")
                break

            event_lines.append(event_line)
            current_length += len(event_line)
            total_shown += 1

        # Check if we showed all events for this day
        if len(events) > 3:
            more_line = f"  ...{len(events) - 3} more\n"
            if current_length + len(more_line) <= available_chars:
                event_lines.append(more_line)
                current_length += len(more_line)

        # Add spacing between days
        if current_length + 1 <= available_chars:
            event_lines.append("\n")
            current_length += 1

    # Combine all parts
    post_text = intro + "".join(event_lines).rstrip() + url_line

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

    # Prepare post data
    data = {
        'status': status_text,
        'visibility': 'public',
    }

    try:
        # Make POST request to Mastodon API
        response = requests.post(api_url, json=data, headers=headers, timeout=30)
        response.raise_for_status()

        # Parse response
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
    """Main function to post weekly event preview to Mastodon."""
    parser = argparse.ArgumentParser(
        description='Post weekly event preview to Mastodon',
        epilog='Requires MASTODON_ACCESS_TOKEN and MASTODON_INSTANCE_URL environment variables'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date of week to preview (YYYY-MM-DD). Defaults to next Monday.'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be posted without actually posting'
    )

    args = parser.parse_args()

    # Determine start date (next Monday)
    if args.start_date:
        try:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        except ValueError:
            print(f"Error: Invalid date format '{args.start_date}'. Use YYYY-MM-DD")
            return 1
    else:
        start_date = get_next_monday()

    end_date = start_date + timedelta(days=6)
    print(f"Creating weekly preview for {start_date.strftime('%A, %B %-d')} - {end_date.strftime('%A, %B %-d, %Y')}...")

    # Load all events
    all_events = load_events()
    if not all_events:
        print("No events data available.")
        return 1

    # Get events for the week
    events_by_date = get_events_for_week(all_events, start_date)

    total_events = sum(len(events) for events in events_by_date.values())
    print(f"Found {total_events} event(s) for the week")

    # Create post text
    post_text = create_weekly_preview_post(events_by_date, start_date, BASE_URL)

    # Post to Mastodon
    success = post_to_mastodon(post_text, dry_run=args.dry_run)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
