#!/usr/bin/env python3
from flask_frozen import Freezer
import os
import calendar
from datetime import datetime, timedelta

# Import app
from app import app
from app import local_tz, get_events, get_upcoming_weeks, get_categories, get_upcoming_months

# Configure Freezer output destination
app.config['FREEZER_DESTINATION'] = 'build'
app.config['FREEZER_RELATIVE_URLS'] = True

freezer = Freezer(app)

@freezer.register_generator
def month_page():
    """Generate URLs for month pages"""
    months = get_upcoming_months()
    for month_data in months:
        yield {'year': month_data['year'], 'month': month_data['month']}

@freezer.register_generator
def region_page():
    """Generate URLs for region pages"""
    yield {'state': 'dc'}
    yield {'state': 'va'}
    yield {'state': 'md'}

@freezer.register_generator
def week_page():
    """Generate URLs for week pages"""
    # Generate pages for 12 weeks ahead
    for week_id in get_upcoming_weeks(12):
        yield {'week_id': week_id}

@freezer.register_generator
def edit_list():
    """Generate the edit events list page"""
    yield {}

@freezer.register_generator
def edit_event_dynamic():
    """Generate the dynamic edit event page"""
    yield {}

@freezer.register_generator
def submit():
    """Generate the event submission page"""
    yield {}

@freezer.register_generator
def locations_index():
    """Generate the locations index page"""
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
def groups_json():
    """Generate the groups JSON endpoint"""
    yield {}

@freezer.register_generator
def edit_groups():
    """Generate the groups edit page"""
    yield {}

@freezer.register_generator
def virtual_events_page():
    """Generate the virtual events page"""
    yield {}

@freezer.register_generator
def category_page():
    """Generate URLs for individual category pages"""
    categories = get_categories()
    for slug in categories.keys():
        yield {'slug': slug}

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

@freezer.register_generator
def events_json():
    """Generate the events JSON file"""
    yield {}

@freezer.register_generator
def ical_feed():
    """Generate the iCal feed"""
    yield {}

@freezer.register_generator
def category_ical_feed():
    """Generate iCal feeds for each category"""
    categories = get_categories()
    for slug in categories.keys():
        yield {'slug': slug}

@freezer.register_generator
def location_ical_feed():
    """Generate iCal feeds for each location"""
    yield {'state': 'dc'}
    yield {'state': 'va'}
    yield {'state': 'md'}

@freezer.register_generator
def category_rss_feed():
    """Generate RSS feeds for each category"""
    categories = get_categories()
    for slug in categories.keys():
        yield {'slug': slug}

@freezer.register_generator
def location_rss_feed():
    """Generate RSS feeds for each location"""
    yield {'state': 'dc'}
    yield {'state': 'va'}
    yield {'state': 'md'}

@freezer.register_generator
def rss_feed():
    """Generate the RSS feed"""
    yield {}

@freezer.register_generator
def not_found_page():
    """Generate the 404 error page"""
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