#!/usr/bin/env python3
import sys
import os
import re
import yaml
import requests
import extruct
from urllib.parse import urlparse
from w3lib.html import get_base_url

def validate_meetup_url(url):
    """Validate that the URL is a valid meetup.com group URL."""
    parsed = urlparse(url)
    if not parsed.netloc.endswith('meetup.com'):
        raise ValueError("URL must be from meetup.com")
    if not parsed.path or parsed.path == '/':
        raise ValueError("URL must point to a specific meetup group")
    return True

def get_group_name_from_jsonld(url):
    """Extract the group name from the event page's JSON-LD data."""
    try:
        # Fetch the webpage
        r = requests.get(url)
        r.raise_for_status()
        
        # Extract JSON-LD data
        base_url = get_base_url(r.text, r.url)
        data = extruct.extract(r.text, base_url=base_url, syntaxes=['json-ld'])
        
        # Look for Event and nested Organization in JSON-LD data
        json_ld = data.get('json-ld', [])
        for item in json_ld:
            if item.get('@type') == 'Event':
                organizer = item.get('organizer', {})
                if isinstance(organizer, dict) and organizer.get('@type') == 'Organization':
                    return organizer.get('name')
        
        raise ValueError("Could not find organization name in JSON-LD data")
    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch URL: {e}")
    except Exception as e:
        raise ValueError(f"Failed to parse JSON-LD data: {e}")

def get_group_name_from_url(url):
    """Extract the group name from the meetup URL."""
    # Parse the URL properly
    parsed = urlparse(url)
    # Get the last part of the path and remove any trailing slash
    group_name = parsed.path.strip('/').split('/')[-1]
    return group_name

def create_group_file(url):
    """Create a YAML file for the meetup group."""
    try:
        validate_meetup_url(url)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    group_name = get_group_name_from_url(url)
    
    # Clean up the URL - ensure no trailing slash
    clean_url = url.rstrip('/')
    
    # Try to get the organization name from JSON-LD data first
    display_name = None
    try:
        display_name = get_group_name_from_jsonld(url)
    except ValueError as e:
        print(f"Warning: Could not extract name from JSON-LD: {e}")
        # Fall back to URL-based name if JSON-LD parsing fails
        # Convert group name to a more readable format
        # First replace dashes and underscores with spaces
        readable_name = group_name.replace('-', ' ').replace('_', ' ')
        # Handle special cases like "dc", "nova", etc.
        words = readable_name.split()
        processed_words = []
        for word in words:
            # Special case for DC, AWS, etc.
            if word.lower() in ['dc', 'aws', 'ux', 'bi', 'ai']:
                processed_words.append(word.upper())
            else:
                processed_words.append(word.capitalize())
        display_name = ' '.join(processed_words)
    
    # Create group data
    group_data = {
        'name': display_name,
        'website': clean_url,
        'rss': f"{clean_url}/events/rss",
        'active': True
    }

    # Create filename - use the group name as is since it's already URL-friendly
    filename = f"{group_name}.yaml"
    filepath = os.path.join('_groups', filename)

    # Check if file already exists
    if os.path.exists(filepath):
        print(f"Error: Group file already exists at {filepath}")
        sys.exit(1)

    # Write the YAML file
    try:
        with open(filepath, 'w') as f:
            yaml.dump(group_data, f, default_flow_style=False, sort_keys=False)
        print(f"Successfully created group file at {filepath}")
    except Exception as e:
        print(f"Error creating group file: {e}")
        sys.exit(1)

def main():
    if len(sys.argv) != 2:
        print("Usage: add_meetup.py <meetup-url>")
        print("Example: add_meetup.py https://www.meetup.com/dc-python-users-group/")
        sys.exit(1)

    url = sys.argv[1]
    create_group_file(url)

if __name__ == '__main__':
    main()