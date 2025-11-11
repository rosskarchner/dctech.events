#!/usr/bin/env python3
"""
Script to parse lu.ma/luma.com event URLs and generate YAML files for single events.
Usage: python add-luma.py <luma_url>
"""

import sys
import requests
import re
import yaml
import os
import json
from datetime import datetime
from bs4 import BeautifulSoup

def clean_filename(title):
    """Create a clean filename from event title."""
    # Convert to lowercase and remove special characters
    filename = re.sub(r'[^\w\s-]', '', title.lower())
    # Replace spaces and hyphens with hyphens
    filename = re.sub(r'[-\s]+', '-', filename)
    return filename[:100]  # Limit length

def parse_luma_url(url):
    """Parse lu.ma/luma.com URL and extract event details."""
    try:
        # Handle both lu.ma and luma.com URLs
        if 'lu.ma/' in url and 'luma.com' not in url:
            # Replace lu.ma with luma.com to avoid redirect
            url = url.replace('lu.ma/', 'luma.com/')

        print(f"Fetching: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find JSON-LD structured data
        script_tags = soup.find_all('script', type='application/ld+json')
        event_data = None

        for script in script_tags:
            try:
                data = json.loads(script.string)
                # Look for Event type
                if data.get('@type') == 'Event':
                    event_data = data
                    break
            except:
                continue

        if not event_data:
            print("Could not find Event structured data. Please enter details manually.")
            title = input("Enter event title: ")
            date_str = input("Enter event date (YYYY-MM-DD): ")
            time_str = input("Enter event time (HH:MM): ")
            location = input("Enter event location: ")
            cost = input("Enter event cost (or 'Free'): ")
            end_date_str = input("Enter end date (YYYY-MM-DD, or leave empty): ") or None
            end_time_str = input("Enter end time (HH:MM, or leave empty): ") or None

            return {
                'title': title,
                'date': date_str,
                'time': time_str,
                'url': url,
                'location': location,
                'cost': cost if cost else None,
                'end_date': end_date_str,
                'end_time': end_time_str,
                'submitted_by': 'anonymous',
                'submitter_link': ''
            }

        # Extract data from JSON-LD
        title = event_data.get('name', 'Unknown Event')

        # Parse start date/time
        start_date_str = event_data.get('startDate', '')
        if start_date_str:
            # Parse ISO 8601 datetime
            dt = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
            date_str = dt.strftime('%Y-%m-%d')
            time_str = dt.strftime('%H:%M')
        else:
            date_str = input("Enter event date (YYYY-MM-DD): ")
            time_str = input("Enter event time (HH:MM): ")

        # Parse end date/time
        end_date_str = event_data.get('endDate', '')
        end_date = None
        end_time = None
        if end_date_str:
            dt_end = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            # Only set end_date if it's different from start date
            if dt_end.date() != dt.date():
                end_date = dt_end.strftime('%Y-%m-%d')
            # Set end time
            end_time = dt_end.strftime('%H:%M')

        # Extract location
        location = ''
        location_data = event_data.get('location', {})
        if isinstance(location_data, dict):
            venue_name = location_data.get('name', '')
            address_data = location_data.get('address', {})

            if isinstance(address_data, dict):
                street = address_data.get('streetAddress', '')
                city = address_data.get('addressLocality', '')
                state = address_data.get('addressRegion', '')

                if venue_name and street and city and state:
                    location = f"{venue_name}, {street}, {city}, {state}"
                elif venue_name:
                    if city and state:
                        location = f"{venue_name}, {city}, {state}"
                    else:
                        location = venue_name
                elif street and city and state:
                    location = f"{street}, {city}, {state}"
                elif city and state:
                    location = f"{city}, {state}"
            elif venue_name:
                location = venue_name

        if not location:
            location = ''

        # Extract cost from offers
        cost = None
        offers = event_data.get('offers', [])
        if isinstance(offers, list) and len(offers) > 0:
            offer = offers[0]
            price = offer.get('price', 0)
            if price == 0 or price == '0':
                cost = 'Free'
            else:
                currency = offer.get('priceCurrency', 'USD')
                cost = f"${price} {currency}"

        # Create event data dict
        result = {
            'title': title,
            'date': date_str,
            'time': time_str,
            'url': url,
            'location': location,
            'cost': cost,
            'submitted_by': 'anonymous',
            'submitter_link': ''
        }

        # Only add end_date and end_time if they exist
        if end_date:
            result['end_date'] = end_date
        if end_time:
            result['end_time'] = end_time

        return result

    except Exception as e:
        print(f"Error parsing URL: {e}")
        import traceback
        traceback.print_exc()
        return None

def create_event_file(event_data):
    """Create YAML file in _single_events directory."""
    # Create filename with date prefix
    date_prefix = event_data['date']
    title_slug = clean_filename(event_data['title'])
    filename = f"{date_prefix}-{title_slug}.yaml"
    filepath = os.path.join('_single_events', filename)

    # Ensure directory exists
    os.makedirs('_single_events', exist_ok=True)

    # Check if file already exists
    if os.path.exists(filepath):
        print(f"File {filepath} already exists. Overwrite? (y/n): ", end='')
        response = input().lower()
        if response != 'y':
            return None

    with open(filepath, 'w') as f:
        yaml.dump(event_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    return filepath

def main():
    if len(sys.argv) != 2:
        print("Usage: python add-luma.py <luma_url>")
        print("Example: python add-luma.py https://lu.ma/oafkbzlh")
        print("         python add-luma.py https://luma.com/oafkbzlh")
        sys.exit(1)

    url = sys.argv[1]

    # Check if URL is from lu.ma or luma.com
    if 'lu.ma/' not in url and 'luma.com/' not in url:
        print("Error: URL must be from lu.ma or luma.com")
        sys.exit(1)

    print(f"Parsing lu.ma URL: {url}")
    event_data = parse_luma_url(url)

    if not event_data:
        print("Failed to parse event data")
        sys.exit(1)

    print(f"\nParsed event:")
    print(f"Title: {event_data['title']}")
    print(f"Date: {event_data['date']}")
    print(f"Time: {event_data['time']}")
    if event_data.get('end_date'):
        print(f"End Date: {event_data['end_date']}")
    if event_data.get('end_time'):
        print(f"End Time: {event_data['end_time']}")
    print(f"Location: {event_data['location']}")
    print(f"Cost: {event_data.get('cost', 'Not specified')}")

    print("\nCreate event file? (y/n): ", end='')
    response = input().lower()
    if response == 'y':
        filepath = create_event_file(event_data)
        if filepath:
            print(f"✓ Created: {filepath}")
        else:
            print("File creation cancelled")
    else:
        print("Event file not created")

if __name__ == "__main__":
    main()
