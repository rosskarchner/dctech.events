#!/usr/bin/env python3
"""
Generate RSS feed of recently added events.

This script reads event metadata from S3 and generates an RSS 2.0 feed
showing the most recently added events.

Environment Variables:
- S3_BUCKET: S3 bucket name for reading event metadata
- AWS_REGION: AWS region (default: us-east-1)

Usage:
    python generate_rss_feed.py > events-feed.xml
    python generate_rss_feed.py --days 7  # Events added in last 7 days
"""

import os
import sys
import yaml
import argparse
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET
from email.utils import formatdate
import pytz

# AWS imports
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    print("Error: boto3 not installed. Run: pip install boto3", file=sys.stderr)
    sys.exit(1)

# Load configuration
CONFIG_FILE = 'config.yaml'
config = {}
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r') as f:
        config = yaml.safe_load(f)

# Get site configuration
SITE_NAME = config.get('site_name', 'DC Tech Events')
TAGLINE = config.get('tagline', 'Technology conferences and meetups in and around Washington, DC')
BASE_URL = config.get('base_url', 'https://dctech.events')

# Define timezone
timezone_name = config.get('timezone', 'US/Eastern')
local_tz = pytz.timezone(timezone_name)

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
            return {}
        raise
    except Exception as e:
        print(f"Error downloading metadata: {e}", file=sys.stderr)
        return {}


def get_recent_events(metadata, days=30):
    """
    Get events added within the last N days.
    
    Args:
        metadata: Event metadata dict from S3
        days: Number of days to look back
        
    Returns:
        List of (event_key, event_data) tuples sorted by first_seen (newest first)
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent = []
    
    for event_key, event_data in metadata.items():
        first_seen = event_data.get('first_seen')
        if not first_seen:
            continue
        
        try:
            first_seen_dt = datetime.fromisoformat(first_seen.replace('Z', '+00:00'))
            if first_seen_dt >= cutoff:
                recent.append((event_key, event_data, first_seen_dt))
        except (ValueError, AttributeError):
            continue
    
    # Sort by first_seen, newest first
    recent.sort(key=lambda x: x[2], reverse=True)
    
    return [(key, data) for key, data, _ in recent]


def generate_rss_feed(events, max_items=50):
    """
    Generate RSS 2.0 feed XML.
    
    Args:
        events: List of (event_key, event_data) tuples
        max_items: Maximum number of items to include
        
    Returns:
        XML string
    """
    # Create RSS root element
    rss = ET.Element('rss', version='2.0')
    rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')
    
    channel = ET.SubElement(rss, 'channel')
    
    # Channel metadata
    ET.SubElement(channel, 'title').text = f"{SITE_NAME} - New Events"
    ET.SubElement(channel, 'link').text = BASE_URL
    ET.SubElement(channel, 'description').text = f"Recently added events from {SITE_NAME}"
    ET.SubElement(channel, 'language').text = 'en-us'
    
    # Self-referencing atom link
    atom_link = ET.SubElement(channel, 'atom:link')
    atom_link.set('href', f"{BASE_URL}/events-feed.xml")
    atom_link.set('rel', 'self')
    atom_link.set('type', 'application/rss+xml')
    
    # Build date (now)
    now_rfc822 = formatdate(timeval=datetime.now(timezone.utc).timestamp(), usegmt=True)
    ET.SubElement(channel, 'lastBuildDate').text = now_rfc822
    
    # Add items
    for event_key, event_data in events[:max_items]:
        item = ET.SubElement(channel, 'item')
        
        title = event_data.get('title', 'Untitled Event')
        event_date = event_data.get('date', '')
        url = event_data.get('url', '')
        first_seen = event_data.get('first_seen', '')
        
        # Title with date
        if event_date:
            try:
                date_obj = datetime.strptime(event_date, '%Y-%m-%d').date()
                date_str = date_obj.strftime('%B %-d, %Y')
                full_title = f"{title} ({date_str})"
            except ValueError:
                full_title = title
        else:
            full_title = title
        
        ET.SubElement(item, 'title').text = full_title
        
        # Link (use event URL or base URL)
        link_url = url if url else BASE_URL
        ET.SubElement(item, 'link').text = link_url
        
        # Description
        desc_parts = []
        if event_date:
            try:
                date_obj = datetime.strptime(event_date, '%Y-%m-%d').date()
                date_str = date_obj.strftime('%B %-d, %Y')
                desc_parts.append(f"Event Date: {date_str}")
            except ValueError:
                pass
        
        if url:
            desc_parts.append(f'<a href="{url}">Event Details</a>')
        
        description = '<br/>'.join(desc_parts) if desc_parts else title
        ET.SubElement(item, 'description').text = description
        
        # GUID (unique identifier)
        guid = ET.SubElement(item, 'guid')
        guid.set('isPermaLink', 'false')
        guid.text = event_key
        
        # Publication date (when it was added to the site)
        if first_seen:
            try:
                first_seen_dt = datetime.fromisoformat(first_seen.replace('Z', '+00:00'))
                pub_date_rfc822 = formatdate(timeval=first_seen_dt.timestamp(), usegmt=True)
                ET.SubElement(item, 'pubDate').text = pub_date_rfc822
            except (ValueError, AttributeError):
                pass
    
    # Convert to XML string with declaration
    tree = ET.ElementTree(rss)
    ET.indent(tree, space='  ')
    
    # Generate XML string
    import io
    output = io.BytesIO()
    tree.write(output, encoding='utf-8', xml_declaration=True)
    return output.getvalue().decode('utf-8')


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate RSS feed of recently added events'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days to look back (default: 30)'
    )
    parser.add_argument(
        '--max-items',
        type=int,
        default=50,
        help='Maximum number of items in feed (default: 50)'
    )
    
    args = parser.parse_args()
    
    # Check S3 bucket is configured
    if not S3_BUCKET:
        print("Error: S3_BUCKET environment variable not set", file=sys.stderr)
        return 1
    
    # Get S3 client and download metadata
    try:
        s3_client = get_s3_client()
    except NoCredentialsError:
        print("Error: AWS credentials not configured", file=sys.stderr)
        return 1
    
    print(f"Downloading metadata from S3...", file=sys.stderr)
    metadata = download_metadata_from_s3(s3_client, S3_BUCKET)
    
    if not metadata:
        print("Warning: No metadata found", file=sys.stderr)
    
    print(f"Finding events added in last {args.days} days...", file=sys.stderr)
    recent_events = get_recent_events(metadata, days=args.days)
    
    print(f"Found {len(recent_events)} recent events", file=sys.stderr)
    print(f"Generating RSS feed...", file=sys.stderr)
    
    # Generate RSS feed
    rss_xml = generate_rss_feed(recent_events, max_items=args.max_items)
    
    # Output to stdout
    print(rss_xml)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
