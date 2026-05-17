#!/usr/bin/env python3
from flask_frozen import Freezer
import os
import sys
from datetime import datetime, timedelta

from app import app
from app import local_tz, get_events, get_upcoming_weeks, get_categories, get_upcoming_months


def create_freezer_with_generators(app_instance):
    """Create a freezer with all route generators registered"""
    freezer = Freezer(app_instance)

    @freezer.register_generator
    def month_page():
        months = get_upcoming_months()
        for month_data in months:
            yield {'year': month_data['year'], 'month': month_data['month']}

    @freezer.register_generator
    def region_page():
        yield {'state': 'dc'}
        yield {'state': 'va'}
        yield {'state': 'md'}

    @freezer.register_generator
    def week_page():
        for week_id in get_upcoming_weeks(12):
            yield {'week_id': week_id}

    @freezer.register_generator
    def locations_index():
        yield {}

    @freezer.register_generator
    def approved_groups_list():
        yield {}

    @freezer.register_generator
    def virtual_events_page():
        yield {}

    @freezer.register_generator
    def category_page():
        categories = get_categories()
        for slug in categories.keys():
            yield {'slug': slug}

    @freezer.register_generator
    def feeds_page():
        yield {}

    @freezer.register_generator
    def sitemap():
        yield {}

    @freezer.register_generator
    def events_json():
        yield {}

    @freezer.register_generator
    def ical_feed():
        yield {}

    @freezer.register_generator
    def category_ical_feed():
        categories = get_categories()
        for slug in categories.keys():
            yield {'slug': slug}

    @freezer.register_generator
    def location_ical_feed():
        yield {'state': 'dc'}
        yield {'state': 'va'}
        yield {'state': 'md'}

    @freezer.register_generator
    def category_rss_feed():
        categories = get_categories()
        for slug in categories.keys():
            yield {'slug': slug}

    @freezer.register_generator
    def location_rss_feed():
        yield {'state': 'dc'}
        yield {'state': 'va'}
        yield {'state': 'md'}

    @freezer.register_generator
    def not_found_page():
        yield {}

    return freezer


if __name__ == '__main__':
    output_dir = 'build/dctech'
    app.config['FREEZER_DESTINATION'] = output_dir
    app.config['FREEZER_RELATIVE_URLS'] = True

    os.makedirs('build', exist_ok=True)

    freezer = create_freezer_with_generators(app)
    freezer.freeze()

    import shutil
    site_categories_src = 'static/categories.json'
    site_categories_dst = f'{output_dir}/static/categories.json'
    if os.path.exists(site_categories_src):
        shutil.copy2(site_categories_src, site_categories_dst)

    print(f"Generated static site to {output_dir}")
