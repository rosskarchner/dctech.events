#!/usr/bin/env python3
"""
Post daily event summary to Bluesky using AT Protocol API.

This script posts a summary of tech events happening today to a Bluesky account.
It only posts if there are events scheduled for the current day.

AT Protocol (Authenticated Transfer Protocol) Details:
- Bluesky uses AT Protocol, a federated social networking protocol
- Authentication via username (handle) and app password
- Posts are called "records" in AT Protocol terminology
- Records are stored in Personal Data Repositories (PDRs)
- Maximum character limit: 300 characters (grapheme count)
- Uses Lexicon schema for data validation
- Uses HTTPS with XRPC (cross-organization RPC) for API calls

AT Protocol Standards in Use:
- AT Protocol: Authenticated Transfer Protocol for federated identity and data
- XRPC: Cross-organization Remote Procedure Call protocol
- Lexicons: Schemas that define the structure of records and API methods
- DIDs (Decentralized Identifiers): For user identity (did:plc: or did:web:)
- Content Addressing: Records are addressed by CID (Content Identifier)
- app.bsky.feed.post: Lexicon for creating posts
- com.atproto.server.createSession: Lexicon for authentication

Environment Variables Required:
- BLUESKY_HANDLE: Your Bluesky handle (e.g., username.bsky.social)
- BLUESKY_APP_PASSWORD: App-specific password (not your main password)

Usage:
    export BLUESKY_HANDLE="your-handle.bsky.social"
    export BLUESKY_APP_PASSWORD="your-app-password"
    python post_to_bluesky.py
    python post_to_bluesky.py --dry-run  # Test without posting
    python post_to_bluesky.py --date 2026-01-15  # Post for specific date
"""

import os
import sys
import yaml
import argparse
from datetime import datetime, date, timezone
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

# Bluesky/AT Protocol configuration
BLUESKY_HANDLE = os.environ.get('BLUESKY_HANDLE')
BLUESKY_APP_PASSWORD = os.environ.get('BLUESKY_APP_PASSWORD')
BLUESKY_API_URL = 'https://bsky.social'  # Main Bluesky PDS (Personal Data Server)

# Character limit for Bluesky (grapheme count)
BLUESKY_CHAR_LIMIT = 300


def load_events():
    """Load events from upcoming.yaml file."""
    if not os.path.exists(UPCOMING_FILE):
        print(f"Warning: {UPCOMING_FILE} not found. Run 'make generate-month-data' first.")
        return []
    
    with open(UPCOMING_FILE, 'r', encoding='utf-8') as f:
        events = yaml.safe_load(f)
        return events if events else []


def is_virtual_event(event):
    """
    Determine if an event is virtual/online (has no physical location).
    
    Args:
        event: Event dictionary
    
    Returns:
        True if event is virtual/online, False if it has a physical location
    """
    location = event.get('location', '')
    
    # If location is empty or None, consider it virtual
    if not location or not location.strip():
        return True
    
    # Check for common virtual/online indicators (case-insensitive)
    location_lower = location.lower()
    virtual_indicators = [
        'virtual', 'online', 'remote', 'zoom', 'webinar', 
        'livestream', 'live stream', 'web', 'internet',
        'https://', 'http://', 'www.'
    ]
    
    for indicator in virtual_indicators:
        if indicator in location_lower:
            return True
    
    return False


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


def format_event_line(event, max_length=80):
    """
    Format a single event as a line of text.
    
    For Bluesky, we just format the title without the URL here.
    The URL will be added as a facet in the post creation.
    
    Args:
        event: Event dictionary
        max_length: Maximum length for the event line
    
    Returns:
        Formatted string for the event
    """
    title = event.get('title', 'Untitled Event')
    
    # Format event line without time
    event_line = f"• {title}"
    
    # Truncate if too long
    if len(event_line) > max_length:
        event_line = event_line[:max_length-3] + "..."
    
    return event_line


def create_bluesky_post(events, target_date, base_url):
    """
    Create a Bluesky post text with facets for clickable links.
    
    Args:
        events: List of events
        target_date: Date for the events
        base_url: Base URL of the website
    
    Returns:
        Tuple of (post_text, facets) where facets is a list of link facets
    """
    # Format date (shorter for Bluesky's limit)
    date_str = target_date.strftime('%b %-d')
    
    # Start building the post
    intro = f"📅 DC tech events today ({date_str}):\n\n"
    
    # We'll build the text and track facets (clickable links)
    post_parts = [intro]
    facets = []
    
    # Add events with clickable titles
    events_shown = 0
    for event in events[:8]:  # Limit to first 8 events
        title = event.get('title', 'Untitled Event')
        url = event.get('url', '')
        
        # Calculate current position in text
        current_text = "".join(post_parts)
        
        # Add bullet and title
        event_line = f"• {title}\n"
        
        # If we have a URL, create a facet for the title
        if url:
            # Find the byte positions for the title (not including bullet)
            title_start = len(current_text.encode('utf-8')) + len("• ".encode('utf-8'))
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
    """Main function to post daily event summary to Bluesky."""
    parser = argparse.ArgumentParser(
        description='Post daily event summary to Bluesky',
        epilog='Requires BLUESKY_HANDLE and BLUESKY_APP_PASSWORD environment variables'
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
    
    # Create post text with facets
    post_text, facets = create_bluesky_post(in_person_events, target_date, BASE_URL)
    
    # Post to Bluesky
    success = post_to_bluesky(post_text, facets=facets, dry_run=args.dry_run)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
