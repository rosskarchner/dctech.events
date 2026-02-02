#!/usr/bin/env python3
"""
Post weekly newsletter to micro.blog using Micropub API.

This script fetches the weekly newsletter from the live deployed site
and posts it to micro.blog every Monday at 7:00 AM EST.

Micropub API Details:
- Endpoint: https://micro.blog/micropub
- Authentication: Bearer token in Authorization header
- Standard: W3C Micropub (https://www.w3.org/TR/micropub/)
- Content-Type: application/json
- Format: Microformats 2 JSON structure
- Required: type (h-entry), properties.content (HTML body), properties.name (title)
- Optional: properties.mp-destination (for multi-blog accounts)

Environment Variables Required:
- MB_TOKEN: App token from micro.blog (Account → App tokens)
- MICROBLOG_DESTINATION: (Optional) Custom domain URL for multi-blog accounts

Usage:
    export MB_TOKEN="your-token-here"
    export MICROBLOG_DESTINATION="https://updates.dctech.events/"
    python post_newsletter_to_microblog.py
    python post_newsletter_to_microblog.py --dry-run  # Test without posting
"""

import os
import sys
import yaml
import argparse
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
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

# Micro.blog API configuration
MB_TOKEN = os.environ.get('MB_TOKEN')
MICROBLOG_DESTINATION = os.environ.get('MICROBLOG_DESTINATION')

# Newsletter URL
NEWSLETTER_URL = f"{BASE_URL}/newsletter.html"

# Micropub endpoint
MICROPUB_ENDPOINT = "https://micro.blog/micropub"


def get_ordinal_suffix(day):
    """
    Get the ordinal suffix for a day number (1st, 2nd, 3rd, 4th, etc.).

    Args:
        day: Integer day of month (1-31)

    Returns:
        String suffix: "st", "nd", "rd", or "th"
    """
    if 10 <= day % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
    return suffix


def generate_newsletter_title(target_date):
    """
    Generate the newsletter title for the given date.

    Format: "DC Tech Events for the week of [Month] [Day][ordinal]"
    Example: "DC Tech Events for the week of February 3rd"

    Args:
        target_date: Date object for Monday of the target week

    Returns:
        String title
    """
    month_name = target_date.strftime('%B')
    day = target_date.day
    ordinal = get_ordinal_suffix(day)

    return f"{SITE_NAME} for the week of {month_name} {day}{ordinal}"


def fetch_newsletter_html(url):
    """
    Fetch the newsletter HTML from the deployed site.

    Args:
        url: Newsletter URL to fetch

    Returns:
        Tuple of (success: bool, content: str or error message)
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return (True, response.text)
    except requests.exceptions.Timeout:
        return (False, f"Timeout fetching newsletter from {url}")
    except requests.exceptions.ConnectionError:
        return (False, f"Connection error fetching newsletter from {url}")
    except requests.exceptions.RequestException as e:
        return (False, f"Error fetching newsletter: {e}")


def extract_body_content(html):
    """
    Extract the innerHTML of the <body> tag from the newsletter HTML.

    Args:
        html: Full HTML string from newsletter page

    Returns:
        String containing body innerHTML, or None if body not found
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')
        body = soup.find('body')

        if not body:
            return None

        # Get innerHTML by extracting all children as strings
        # This preserves all HTML tags within the body
        return ''.join(str(child) for child in body.children)

    except Exception as e:
        print(f"Error parsing HTML: {e}")
        return None


def post_to_microblog(title, content, token, destination=None, dry_run=False):
    """
    Post content to micro.blog using Micropub API with JSON syntax.

    Args:
        title: Post title (h-entry name)
        content: Post HTML content (h-entry content)
        token: Micro.blog app token
        destination: Optional destination URL for multi-blog accounts
        dry_run: If True, print what would be posted without actually posting

    Returns:
        True if successful, False otherwise
    """
    if dry_run:
        print("\n=== DRY RUN - Would post to micro.blog ===")
        print(f"Endpoint: {MICROPUB_ENDPOINT}")
        print(f"Title: {title}")
        print(f"Content length: {len(content)} characters")
        if destination:
            print(f"Destination: {destination}")
        print(f"\nContent preview (first 500 chars):")
        print(content[:500])
        if len(content) > 500:
            print("...")
        print("\n=== End of dry run ===\n")
        return True

    if not token:
        print("Error: MB_TOKEN environment variable must be set")
        print("Get your app token from: https://micro.blog/account/apps")
        return False

    # Prepare headers with Bearer token for JSON request
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }

    # Prepare JSON payload using Microformats 2 structure
    # According to W3C Micropub spec: https://www.w3.org/TR/micropub/
    # For HTML content, use an object with 'html' key per spec section 3.3.2
    payload = {
        'type': ['h-entry'],
        'properties': {
            'name': [title],
            'content': [{'html': content}],
        }
    }

    # Add destination if provided (for multi-blog accounts)
    if destination:
        payload['properties']['mp-destination'] = [destination]

    try:
        # Make POST request to Micropub endpoint with JSON payload
        response = requests.post(
            MICROPUB_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        # Get the Location header with the new post URL
        post_url = response.headers.get('Location', 'posted successfully')

        print(f"✓ Successfully posted to micro.blog: {post_url}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"✗ Error posting to micro.blog: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        return False


def main():
    """Main function to post weekly newsletter to micro.blog."""
    parser = argparse.ArgumentParser(
        description='Post weekly newsletter to micro.blog',
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

    # Calculate the Monday of this week (for the title)
    days_since_monday = current_date.weekday()  # 0 = Monday, 6 = Sunday
    monday_date = current_date - timedelta(days=days_since_monday)

    print(f"Posting newsletter for the week of {monday_date.strftime('%A, %B %-d, %Y')}...")

    # Generate title
    title = generate_newsletter_title(monday_date)
    print(f"Title: {title}")

    # Fetch newsletter HTML
    print(f"Fetching newsletter from {NEWSLETTER_URL}...")
    success, html = fetch_newsletter_html(NEWSLETTER_URL)

    if not success:
        print(f"Error: {html}")
        return 1

    print("✓ Newsletter fetched successfully")

    # Extract body content
    body_content = extract_body_content(html)

    if not body_content:
        print("Error: Could not find <body> tag in newsletter HTML")
        return 1

    if not body_content.strip():
        print("Warning: Newsletter body is empty. Skipping post.")
        return 0

    print(f"✓ Extracted body content ({len(body_content)} characters)")

    # Post to micro.blog
    success = post_to_microblog(
        title=title,
        content=body_content,
        token=MB_TOKEN,
        destination=MICROBLOG_DESTINATION,
        dry_run=args.dry_run
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
