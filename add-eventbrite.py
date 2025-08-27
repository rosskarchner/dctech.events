#!/usr/bin/env python3
"""
Script to parse Eventbrite event URLs and generate YAML files for single events.
Usage: python add-eventbrite.py <eventbrite_url>
"""

import sys
import requests
import re
import yaml
import os
from datetime import datetime
from bs4 import BeautifulSoup

def clean_filename(title):
    """Create a clean filename from event title."""
    # Remove special characters and replace spaces with underscores
    filename = re.sub(r'[^\w\s-]', '', title.lower())
    filename = re.sub(r'[-\s]+', '_', filename)
    return filename[:50]  # Limit length

def parse_eventbrite_url(url):
    """Parse Eventbrite URL and extract event details."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find JSON-LD structured data
        script_tags = soup.find_all('script', type='application/ld+json')
        event_data = None
        
        for script in script_tags:
            try:
                import json
                data = json.loads(script.string)
                # Look for Event, EducationEvent, or BusinessEvent type
                if data.get('@type') in ['Event', 'EducationEvent', 'BusinessEvent']:
                    event_data = data
                    break
            except:
                continue
        
        if event_data:
            # Extract data from JSON-LD
            title = event_data.get('name', 'Unknown Event')
            description = event_data.get('description', '')[:200] + "..." if event_data.get('description') else ""
            
            # Parse start date/time
            start_date = event_data.get('startDate', '')
            if start_date:
                dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                date_str = dt.strftime('%Y-%m-%d')
                time_str = dt.strftime('%H:%M')
            else:
                date_str = input("Enter event date (YYYY-MM-DD): ")
                time_str = input("Enter event time (HH:MM): ")
            
            # Extract location
            location_data = event_data.get('location', {})
            if isinstance(location_data, dict):
                venue_name = location_data.get('name', '')
                address_data = location_data.get('address', {})
                if isinstance(address_data, dict):
                    street = address_data.get('streetAddress', '')
                    city = address_data.get('addressLocality', '')
                    state = address_data.get('addressRegion', '')
                    
                    if venue_name:
                        location = venue_name
                        if city and state:
                            location += f", {city}, {state}"
                    elif street and city and state:
                        location = f"{street}, {city}, {state}"
                    else:
                        location = str(address_data.get('streetAddress', ''))
                else:
                    location = venue_name
            else:
                location = str(location_data) if location_data else ""
            
            if not location:
                location = input("Enter event location: ")
        else:
            # Fallback to manual input if no JSON-LD found
            print("Could not find structured data. Please enter details manually.")
            title = input("Enter event title: ")
            description = input("Enter event description: ")[:200] + "..."
            date_str = input("Enter event date (YYYY-MM-DD): ")
            time_str = input("Enter event time (HH:MM): ")
            location = input("Enter event location: ")
        
        return {
            'title': title,
            'description': description,
            'date': date_str,
            'time': time_str,
            'url': url,
            'location': location
        }
        
    except Exception as e:
        print(f"Error parsing URL: {e}")
        return None

def create_event_file(event_data):
    """Create YAML file in _single_events directory."""
    filename = clean_filename(event_data['title']) + '.yaml'
    filepath = os.path.join('_single_events', filename)
    
    # Ensure directory exists
    os.makedirs('_single_events', exist_ok=True)
    
    # Check if file already exists
    if os.path.exists(filepath):
        print(f"File {filepath} already exists. Overwrite? (y/n): ", end='')
        if input().lower() != 'y':
            return None
    
    with open(filepath, 'w') as f:
        yaml.dump(event_data, f, default_flow_style=False, sort_keys=False)
    
    return filepath

def main():
    if len(sys.argv) != 2:
        print("Usage: python add-eventbrite.py <eventbrite_url>")
        sys.exit(1)
    
    url = sys.argv[1]
    
    if 'eventbrite.com' not in url:
        print("Error: URL must be from eventbrite.com")
        sys.exit(1)
    
    print(f"Parsing Eventbrite URL: {url}")
    event_data = parse_eventbrite_url(url)
    
    if not event_data:
        print("Failed to parse event data")
        sys.exit(1)
    
    print(f"\nParsed event:")
    print(f"Title: {event_data['title']}")
    print(f"Date: {event_data['date']}")
    print(f"Time: {event_data['time']}")
    print(f"Location: {event_data['location']}")
    print(f"Description: {event_data['description'][:100]}...")
    
    print("\nCreate event file? (y/n): ", end='')
    if input().lower() == 'y':
        filepath = create_event_file(event_data)
        if filepath:
            print(f"Created: {filepath}")
        else:
            print("File creation cancelled")
    else:
        print("Event file not created")

if __name__ == "__main__":
    main()