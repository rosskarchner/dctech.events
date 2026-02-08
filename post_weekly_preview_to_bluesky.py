#!/usr/bin/env python3
"""
Post weekly event preview to Bluesky using AT Protocol API.

This script posts a preview of tech events happening in the upcoming week to a Bluesky account.
Designed to run on Thursday afternoons to preview the following week (Monday-Sunday).

AT Protocol (Authenticated Transfer Protocol) Details:
- Bluesky uses AT Protocol, a federated social networking protocol
- Authentication via username (handle) and app password
- Posts are called "records" in AT Protocol terminology
- Records are stored in Personal Data Repositories (PDRs)
- Maximum character limit: 300 characters (grapheme count)
- Uses Lexicon schema for data validation
- Uses HTTPS with XRPC (cross-organization RPC) for API calls

Environment Variables Required:
- BLUESKY_HANDLE: Your Bluesky handle (e.g., username.bsky.social)
- BLUESKY_APP_PASSWORD: App-specific password (not your main password)

Usage:
    export BLUESKY_HANDLE="your-handle.bsky.social"
    export BLUESKY_APP_PASSWORD="your-app-password"
    python post_weekly_preview_to_bluesky.py
    python post_weekly_preview_to_bluesky.py --dry-run  # Test without posting
    python post_weekly_preview_to_bluesky.py --start-date 2026-01-13  # Custom week start
"""

import os
import sys
import yaml
import argparse
from datetime import datetime, date, timedelta, timezone
import requests
import pytz
from pathlib import Path
from collections import defaultdict
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

# Data paths
DATA_DIR = '_data'
UPCOMING_FILE = os.path.join(DATA_DIR, 'upcoming.yaml')

# Bluesky/AT Protocol configuration
BLUESKY_HANDLE = os.environ.get('BLUESKY_HANDLE')
BLUESKY_APP_PASSWORD = os.environ.get('BLUESKY_APP_PASSWORD')
BLUESKY_API_URL = 'https://bsky.social'  # Main Bluesky PDS (Personal Data Server)

# Character limit for Bluesky (grapheme count)
BLUESKY_CHAR_LIMIT = 300


def load_events():
    """Load events from DynamoDB."""
    events = db_utils.get_future_events()
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
    Create a Bluesky post text with facets for clickable links.

    Args:
        events_by_date: Dictionary mapping date strings to list of events
        start_date: Start date of the week
        base_url: Base URL of the website

    Returns:
        Tuple of (post_text, facets) where facets is a list of link facets
    """
    end_date = start_date + timedelta(days=6)

    # Count total events
    total_events = sum(len(events) for events in events_by_date.values())

    # Build intro (shorter for Bluesky)
    date_range = f"{start_date.strftime('%b %-d')}-{end_date.strftime('%-d')}"

    if total_events == 0:
        # No events message
        post_text = f"📅 Week of {date_range}: No DC tech events scheduled yet. Check {base_url}"

        # Create facet for base URL
        base_url_start = len(post_text.encode('utf-8')) - len(base_url.encode('utf-8'))
        base_url_end = len(post_text.encode('utf-8'))

        facets = [{
            'index': {
                'byteStart': base_url_start,
                'byteEnd': base_url_end
            },
            'features': [{
                '$type': 'app.bsky.richtext.facet#link',
                'uri': base_url
            }]
        }]

        return post_text, facets

    intro = f"📅 Next week ({date_range}) - {total_events} event{'s' if total_events != 1 else ''}:\n\n"

    # We'll build the text and track facets (clickable links)
    post_parts = [intro]
    facets = []

    # Sort dates
    sorted_dates = sorted(events_by_date.keys())

    events_shown = 0
    max_events_total = 5  # Limit total events shown due to char limit

    for date_str in sorted_dates:
        events = events_by_date[date_str]
        event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        day_name = event_date.strftime('%a')  # Mon, Tue, etc.

        # Show first event for each day, but limit total
        for event in events[:1]:  # Max 1 event per day
            if events_shown >= max_events_total:
                break

            title = event.get('title', 'Untitled Event')
            url = event.get('url', '')

            # Calculate current position in text
            current_text = "".join(post_parts)

            # Format: Day: Title
            event_line = f"{day_name}: {title}\n"

            # If we have a URL, create a facet for the title
            if url:
                # Find the byte positions for the title
                title_start = len(current_text.encode('utf-8')) + len(f"{day_name}: ".encode('utf-8'))
                title_end = title_start + len(title.encode('utf-8'))

                facets.append({
                    'index': {
                        'byteStart': title_start,
                        'byteEnd': title_end
                    },
                    'features': [{
                        '$type': 'app.bsky.richtext.facet#link',
                        'uri': url
                    }]
                })

            post_parts.append(event_line)
            events_shown += 1

        if events_shown >= max_events_total:
            break

    # Add "more" indicator if needed
    if total_events > events_shown:
        remaining = total_events - events_shown
        post_parts.append(f"\n+{remaining} more\n")

    # Add base URL at the end
    post_parts.append(f"\n{base_url}")

    # Create facet for the base URL
    final_text = "".join(post_parts)
    base_url_start = len(final_text.encode('utf-8')) - len(base_url.encode('utf-8'))
    base_url_end = len(final_text.encode('utf-8'))

    facets.append({
        'index': {
            'byteStart': base_url_start,
            'byteEnd': base_url_end
        },
        'features': [{
            '$type': 'app.bsky.richtext.facet#link',
            'uri': base_url
        }]
    })

    return final_text, facets


def create_bluesky_session(handle, app_password):
    """
    Create an authenticated session with Bluesky using AT Protocol.

    Args:
        handle: Bluesky handle (e.g., username.bsky.social)
        app_password: App-specific password

    Returns:
        Tuple of (access_jwt, did) if successful, (None, None) otherwise
    """
    # Use XRPC endpoint for session creation
    session_url = f"{BLUESKY_API_URL}/xrpc/com.atproto.server.createSession"

    # Prepare credentials
    credentials = {
        'identifier': handle,
        'password': app_password
    }

    try:
        # Create session using AT Protocol
        response = requests.post(session_url, json=credentials, timeout=30)
        response.raise_for_status()

        # Parse session data
        session_data = response.json()
        access_jwt = session_data.get('accessJwt')
        did = session_data.get('did')

        if not access_jwt or not did:
            print("Error: Session created but missing access token or DID")
            return None, None

        return access_jwt, did

    except requests.exceptions.RequestException as e:
        print(f"Error creating Bluesky session: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return None, None


def post_to_bluesky(post_text, facets=None, dry_run=False):
    """
    Post to Bluesky using AT Protocol.

    Args:
        post_text: Text content to post
        facets: List of facets (for clickable links, mentions, etc.)
        dry_run: If True, print what would be posted without actually posting

    Returns:
        True if successful, False otherwise
    """
    if dry_run:
        handle = BLUESKY_HANDLE or "username.bsky.social"
        print("\n=== DRY RUN - Would post to Bluesky ===")
        print(f"Handle: {handle}")
        print(f"Post length: {len(post_text)} characters")
        print(f"\n{post_text}")
        if facets:
            print(f"\nWith {len(facets)} clickable link(s)")
        print("\n=== End of dry run ===\n")
        return True

    if not BLUESKY_HANDLE or not BLUESKY_APP_PASSWORD:
        print("Error: BLUESKY_HANDLE and BLUESKY_APP_PASSWORD environment variables must be set")
        return False

    # Create authenticated session
    print("Authenticating with Bluesky...")
    access_jwt, did = create_bluesky_session(BLUESKY_HANDLE, BLUESKY_APP_PASSWORD)

    if not access_jwt:
        return False

    # Prepare post record using app.bsky.feed.post lexicon
    # AT Protocol uses ISO 8601 timestamps with timezone
    now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    # Create post record according to app.bsky.feed.post lexicon
    post_record = {
        '$type': 'app.bsky.feed.post',
        'text': post_text,
        'createdAt': now,
    }

    # Add facets if provided (for clickable links)
    if facets:
        post_record['facets'] = facets

    # Prepare the full record create request
    create_record_data = {
        'repo': did,  # The user's DID (repository identifier)
        'collection': 'app.bsky.feed.post',  # Collection type for posts
        'record': post_record,
    }

    # XRPC endpoint for creating records
    create_url = f"{BLUESKY_API_URL}/xrpc/com.atproto.repo.createRecord"

    # Prepare headers with JWT bearer token
    headers = {
        'Authorization': f'Bearer {access_jwt}',
        'Content-Type': 'application/json',
    }

    try:
        # Create the post record via XRPC
        response = requests.post(create_url, json=create_record_data, headers=headers, timeout=30)
        response.raise_for_status()

        # Parse response (includes CID and URI of created record)
        result = response.json()
        post_uri = result.get('uri', '')
        post_cid = result.get('cid', '')

        print(f"✓ Successfully posted to Bluesky")
        print(f"  URI: {post_uri}")
        print(f"  CID: {post_cid}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"✗ Error posting to Bluesky: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return False


def main():
    """Main function to post weekly event preview to Bluesky."""
    parser = argparse.ArgumentParser(
        description='Post weekly event preview to Bluesky',
        epilog='Requires BLUESKY_HANDLE and BLUESKY_APP_PASSWORD environment variables'
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

    # Create post text with facets
    post_text, facets = create_weekly_preview_post(events_by_date, start_date, BASE_URL)

    # Post to Bluesky
    success = post_to_bluesky(post_text, facets=facets, dry_run=args.dry_run)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
