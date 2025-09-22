#!/usr/bin/env python3
from flask_frozen import Freezer
from app import app, local_tz, get_events, filter_events_by_location
from location_utils import extract_location_info
import os
import calendar
from datetime import datetime, timedelta

# Configure Freezer
app.config['FREEZER_DESTINATION'] = 'build'
app.config['FREEZER_RELATIVE_URLS'] = True

freezer = Freezer(app)

@freezer.register_generator
def region_page():
    """Generate URLs for region pages"""
    yield {'state': 'dc'}
    yield {'state': 'va'}
    yield {'state': 'md'}

@freezer.register_generator
def city_page():
    """Generate URLs for city pages with events"""
    events = get_events()
    cities = set()
    
    for event in events:
        city, state = extract_location_info(event.get('location', ''))
        if city and state in ['DC', 'VA', 'MD']:
            # Skip Washington, DC since it's the same as the DC region
            if not (city == 'Washington' and state == 'DC'):
                cities.add((city, state))
    
    for city, state in cities:
        # Check if city has events
        city_events = filter_events_by_location(events, city=city, state=state)
        if len(city_events) > 0:
            city_slug = city.lower().replace(' ', '-')
            yield {'state': state.lower(), 'city': city_slug}

if __name__ == '__main__':
    freezer.freeze()
    print(f"Static site generated in {app.config['FREEZER_DESTINATION']}")