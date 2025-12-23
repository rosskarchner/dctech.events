#!/usr/bin/env python3
from flask_frozen import Freezer
import os
import calendar
from datetime import datetime, timedelta

# Import app
from app import app
from app import local_tz, get_events, get_upcoming_weeks

# Configure Freezer output destination
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
def virtual_events_page():
    """Generate the virtual events page"""
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

@freezer.register_generator
def ical_feed():
    """Generate the iCal feed"""
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