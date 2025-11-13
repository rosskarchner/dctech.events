#!/usr/bin/env python3
from flask_frozen import Freezer
import argparse
import os
import calendar
from datetime import datetime, timedelta

# Parse command line arguments (must be done before importing app)
parser = argparse.ArgumentParser(description='Generate static site for a specific city or homepage')
parser.add_argument('--city', default='dc', help='City slug (default: dc)')
parser.add_argument('--homepage', action='store_true', help='Generate localtech.events homepage instead of city site')
args = parser.parse_args()

# Import app after parsing args (app.py reads sys.argv)
from app import app, args as app_args
from location_utils import extract_location_info

# Import city-specific functions only if not building homepage
if not args.homepage:
    from app import local_tz, get_events, filter_events_by_location, get_upcoming_weeks

# Configure Freezer output destination
if args.homepage:
    # Homepage goes to build/
    app.config['FREEZER_DESTINATION'] = 'build'
elif args.city == 'dc':
    # DC goes to build/ for backward compatibility with GitHub Pages
    app.config['FREEZER_DESTINATION'] = 'build'
else:
    # Other cities go to build/{city-slug}/
    app.config['FREEZER_DESTINATION'] = os.path.join('build', args.city)

app.config['FREEZER_RELATIVE_URLS'] = True

freezer = Freezer(app)

if not args.homepage:
    # Only generate these pages for city sites, not the homepage
    @freezer.register_generator
    def region_page():
        """Generate URLs for region pages (DC only)"""
        # Only generate region pages for DC
        if args.city == 'dc':
            yield {'state': 'dc'}
            yield {'state': 'va'}
            yield {'state': 'md'}

    @freezer.register_generator
    def city_page():
        """Generate URLs for city pages with events"""
        # Only generate city pages for DC (multi-region support)
        if args.city == 'dc':
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

    @freezer.register_generator
    def week_page():
        """Generate URLs for week pages"""
        # Generate pages for 12 weeks ahead
        for week_id in get_upcoming_weeks(12):
            yield {'week_id': week_id}

    @freezer.register_generator
    def submit():
        """Generate the event submission page"""
        yield {}

    @freezer.register_generator
    def locations_index():
        """Generate the locations index page (DC only)"""
        # Only generate for DC (multi-region support)
        if args.city == 'dc':
            yield {}

    @freezer.register_generator
    def approved_groups_list():
        """Generate the groups page"""
        yield {}

    @freezer.register_generator
    def submit_group():
        """Generate the group submission page"""
        yield {}

    @freezer.register_generator
    def newsletter_html():
        """Generate the HTML newsletter page"""
        yield {}

    @freezer.register_generator
    def newsletter_text():
        """Generate the text newsletter page"""
        yield {}

    @freezer.register_generator
    def sitemap():
        """Generate the sitemap.xml page"""
        yield {}

# Image generation temporarily disabled
# @freezer.register_generator
# def week_image():
#     """Generate URLs for week calendar images"""
#     # Generate images for 12 weeks ahead
#     for week_id in get_upcoming_weeks(12):
#         yield {'week_id': week_id}

if __name__ == '__main__':
    freezer.freeze()
    print(f"Static site generated in {app.config['FREEZER_DESTINATION']}")