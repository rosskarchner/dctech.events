#!/usr/bin/env python3
"""
Generate RSS feed of recently added events.

This script fetches recently added events from DynamoDB and generates an RSS 2.0 feed.

Usage:
    python generate_rss_feed.py > events-feed.xml
    python generate_rss_feed.py --max-items 50
"""

import os
import sys
import yaml
import argparse
from datetime import datetime, timezone
from xml.etree import ElementTree as ET
from email.utils import formatdate
import pytz
import db_utils

# Load configuration
CONFIG_FILE = 'config.yaml'
config = {}
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r') as f:
        config = yaml.safe_load(f)

# Get site configuration
SITE_NAME = config.get('site_name', 'DC Tech Events')
BASE_URL = config.get('base_url', 'https://dctech.events')

# Define timezone
timezone_name = config.get('timezone', 'US/Eastern')
local_tz = pytz.timezone(timezone_name)

def generate_rss_feed(events, max_items=50):
    """
    Generate RSS 2.0 feed XML.
    
    Args:
        events: List of event dictionaries
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
    for event in events[:max_items]:
        item = ET.SubElement(channel, 'item')
        
        title = event.get('title', 'Untitled Event')
        event_date = event.get('date', '')
        url = event.get('url', '')
        # createdAt is the DynamoDB attribute for first seen
        first_seen = event.get('createdAt', '')
        event_key = event.get('eventId', event.get('guid', ''))
        
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
                # first_seen is ISO format from DB
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
        '--max-items',
        type=int,
        default=50,
        help='Maximum number of items in feed (default: 50)'
    )
    
    args = parser.parse_args()
    
    print(f"Fetching recently added events from DynamoDB...", file=sys.stderr)
    recent_events = db_utils.get_recently_added(limit=args.max_items)
    
    print(f"Found {len(recent_events)} recent events", file=sys.stderr)
    print(f"Generating RSS feed...", file=sys.stderr)
    
    # Generate RSS feed
    rss_xml = generate_rss_feed(recent_events, max_items=args.max_items)
    
    # Output to stdout
    print(rss_xml)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())