#!/usr/bin/env python3
"""
Post weekly newsletter note to micro.blog using Micropub API.

This script posts a short note linking to the weekly events page
on micro.blog every Monday at 7:00 AM EST.

Micropub API Details:
- Endpoint: https://micro.blog/micropub
- Authentication: Bearer token in Authorization header
- Format: Form-encoded (h=entry, content=..., mp-destination=...)
- No 'name' field → creates a "note" (not an "article")

Environment Variables Required:
- MB_TOKEN: App token from micro.blog (Account → App tokens)
- MICROBLOG_DESTINATION: (Optional) Custom domain URL for multi-blog accounts
                         Defaults to https://updates.dctech.events/

Usage:
    export MB_TOKEN="your-token-here"
    # MICROBLOG_DESTINATION is optional - defaults to https://updates.dctech.events/
    python post_newsletter_to_microblog.py
    python post_newsletter_to_microblog.py --dry-run  # Test without posting
"""

import os
import sys
import yaml
import argparse
from datetime import datetime, timedelta
import requests
import pytz

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

# Micropub endpoint
MICROPUB_ENDPOINT = "https://micro.blog/micropub"


def get_week_identifier(target_date):
    """
    Get the ISO week identifier (YYYY-Www) for a given date.

    Args:
        target_date: A date object

    Returns:
        String in format YYYY-Www (e.g., "2026-W06")
    """
    iso_year, iso_week, _ = target_date.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def get_week_url(target_date):
    """
    Get the full URL for the weekly events page.

    Args:
        target_date: A date object (typically Monday of the week)

    Returns:
        URL string like "https://dctech.events/week/2026-W06/"
    """
    week_id = get_week_identifier(target_date)
    return f"{BASE_URL}/week/{week_id}/"


def format_short_date(target_date):
    """
    Format a date as M/D/YY (no leading zeros).

    Args:
        target_date: A date object

    Returns:
        String like "2/3/26"
    """
    return f"{target_date.month}/{target_date.day}/{target_date.strftime('%y')}"


def generate_note_content(target_date):
    """
    Generate the note content for the weekly post.

    Args:
        target_date: A date object (Monday of the week)

    Returns:
        String like "DC Tech Events for the week of 2/3/26: https://dctech.events/week/2026-W06/"
    """
    short_date = format_short_date(target_date)
    week_url = get_week_url(target_date)
    return f"{SITE_NAME} for the week of {short_date}: {week_url}"


def post_to_microblog(content, token, destination=None, dry_run=False):
    """
    Post a note to micro.blog using form-encoded Micropub.

    Args:
        content: Plain text note content
        token: Micro.blog app token
        destination: Optional destination URL for multi-blog accounts
        dry_run: If True, print what would be posted without actually posting

    Returns:
        True if successful, False otherwise
    """
    if dry_run:
        print("\n=== DRY RUN - Would post to micro.blog ===")
        print(f"Endpoint: {MICROPUB_ENDPOINT}")
        print(f"Content: {content}")
        if destination:
            print(f"Destination: {destination}")
        print("=== End of dry run ===\n")
        return True

    if not token:
        print("Error: MB_TOKEN environment variable must be set")
        print("Get your app token from: https://micro.blog/account/apps")
        return False

    headers = {
        'Authorization': f'Bearer {token}',
    }

    # Form-encoded payload — no 'name' so it posts as a note
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
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        return False


def main():
    """Main function to post weekly newsletter note to micro.blog."""
    parser = argparse.ArgumentParser(
        description='Post weekly newsletter note to micro.blog',
        epilog='Requires MB_TOKEN environment variable. Optional: MICROBLOG_DESTINATION'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be posted without actually posting'
    )

    args = parser.parse_args()

    # Get current date in configured timezone (should be a Monday)
    current_date = datetime.now(local_tz).date()

    # Calculate the Monday of this week
    days_since_monday = current_date.weekday()  # 0 = Monday, 6 = Sunday
    monday_date = current_date - timedelta(days=days_since_monday)

    print(f"Posting newsletter note for the week of {monday_date.strftime('%A, %B %-d, %Y')}...")

    # Generate note content
    content = generate_note_content(monday_date)
    print(f"Content: {content}")

    # Post to micro.blog
    success = post_to_microblog(
        content=content,
        token=MB_TOKEN,
        destination=MICROBLOG_DESTINATION,
        dry_run=args.dry_run
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
