#!/usr/bin/env python3
"""
Post daily summary of newly added events to micro.blog.

This script:
1. Checks for new events added today by reading S3 metadata
2. Posts a summary to micro.blog if there are new events
3. Format: "X new events added on [Month Day, Year]"

Environment Variables Required:
- MB_TOKEN: App token from micro.blog (Account → App tokens)
- MICROBLOG_DESTINATION: (Optional) Custom domain URL for multi-blog accounts
- S3_BUCKET: S3 bucket name for reading event metadata
- AWS_REGION: AWS region (default: us-east-1)

Usage:
    export MB_TOKEN="your-token-here"
    export MICROBLOG_DESTINATION="https://updates.dctech.events/"
    export S3_BUCKET="your-bucket-name"
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

# AWS imports
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    print("Error: boto3 not installed. Run: pip install boto3")
    sys.exit(1)

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
MICROPUB_ENDPOINT = "https://micro.blog/micropub"

# S3 configuration
S3_BUCKET = os.environ.get('S3_BUCKET', '')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
METADATA_KEY = 'upcoming-history/metadata.json'


def get_s3_client():
    """Get configured S3 client."""
    return boto3.client('s3', region_name=AWS_REGION)


def download_metadata_from_s3(s3_client, bucket):
    """Download metadata.json from S3."""
    try:
        response = s3_client.get_object(Bucket=bucket, Key=METADATA_KEY)
        content = response['Body'].read().decode('utf-8')
        import json
        return json.loads(content)
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            print("No metadata found in S3")
            return {}
        raise
    except Exception as e:
        print(f"Error downloading metadata: {e}")
        return {}


def get_todays_new_events(metadata, target_date=None):
    """
    Get events that were first seen on the target date.
    
    Args:
        metadata: Event metadata dict from S3
        target_date: Date to check (defaults to today in local timezone)
        
    Returns:
        List of events added on target_date
    """
    if target_date is None:
        # Get current date in local timezone
        target_date = datetime.now(local_tz).date()
    
    new_events = []
    
    for event_key, event_data in metadata.items():
        first_seen = event_data.get('first_seen')
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
                new_events.append(event_data)
        except (ValueError, AttributeError) as e:
            print(f"Warning: Could not parse timestamp for {event_key}: {e}")
            continue
    
    return new_events


def generate_summary_html(new_events, target_date):
    """
    Generate HTML summary of new events.
    
    Args:
        new_events: List of new event data dicts
        target_date: Date the events were added
        
    Returns:
        HTML string
    """
    # Sort events by date
    sorted_events = sorted(new_events, key=lambda e: e.get('date', ''))
    
    # Build HTML
    html_parts = [
        f'<p>{len(new_events)} new events have been added to <a href="{BASE_URL}">{SITE_NAME}</a>:</p>',
        '<ul>'
    ]
    
    for event in sorted_events:
        title = event.get('title', 'Untitled Event')
        date = event.get('date', '')
        url = event.get('url', '')
        
        # Format date nicely if available
        date_display = ''
        if date:
            try:
                event_date = datetime.strptime(date, '%Y-%m-%d').date()
                date_display = f" - {event_date.strftime('%B %-d, %Y')}"
            except ValueError:
                pass
        
        if url:
            html_parts.append(f'  <li><a href="{url}">{title}</a>{date_display}</li>')
        else:
            html_parts.append(f'  <li>{title}{date_display}</li>')
    
    html_parts.append('</ul>')
    
    return '\n'.join(html_parts)


def generate_title(count, target_date):
    """
    Generate post title.
    
    Format: "X new events added on May 3rd 2026"
    
    Args:
        count: Number of events
        target_date: Date object
        
    Returns:
        Title string
    """
    # Get ordinal suffix for day
    day = target_date.day
    if 10 <= day % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
    
    month = target_date.strftime('%B')
    year = target_date.year
    
    # Pluralize "event" if needed
    event_word = 'event' if count == 1 else 'events'
    
    return f"{count} new {event_word} added on {month} {day}{suffix} {year}"


def post_to_microblog(title, content, token, destination=None, dry_run=False):
    """
    Post content to micro.blog using form-encoded Micropub.

    Args:
        title: Post title (h-entry name)
        content: Post HTML content
        token: Micro.blog app token
        destination: Optional destination URL
        dry_run: If True, print what would be posted

    Returns:
        True if successful, False otherwise
    """
    if dry_run:
        print("\n=== DRY RUN - Would post to micro.blog ===")
        print(f"Endpoint: {MICROPUB_ENDPOINT}")
        print(f"Title: {title}")
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

    # Form-encoded payload
    data = {
        'h': 'entry',
        'name': title,
        'content[html]': content,
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
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Post daily summary of new events to micro.blog',
        epilog='Requires MB_TOKEN and S3_BUCKET environment variables'
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
    
    # Check S3 bucket is configured
    if not S3_BUCKET:
        print("Error: S3_BUCKET environment variable not set")
        return 1
    
    # Get S3 client and download metadata
    try:
        s3_client = get_s3_client()
    except NoCredentialsError:
        print("Error: AWS credentials not configured")
        return 1
    
    metadata = download_metadata_from_s3(s3_client, S3_BUCKET)
    
    if not metadata:
        print("No metadata found, nothing to post")
        return 0
    
    # Get events added today
    new_events = get_todays_new_events(metadata, target_date)
    
    if not new_events:
        print(f"No new events found for {target_date.strftime('%B %-d, %Y')}")
        print("Nothing to post.")
        return 0
    
    print(f"Found {len(new_events)} new events")
    
    # Generate title and content
    title = generate_title(len(new_events), target_date)
    content = generate_summary_html(new_events, target_date)
    
    print(f"Post title: {title}")
    
    # Post to micro.blog
    success = post_to_microblog(
        title=title,
        content=content,
        token=MB_TOKEN,
        destination=MICROBLOG_DESTINATION,
        dry_run=args.dry_run
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
