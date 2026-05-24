#!/usr/bin/env python3
from flask_frozen import Freezer
import os

from calgen.app import (
    create_app, get_events, get_upcoming_weeks, get_categories, get_upcoming_months,
)
from calgen.site_config import get_config


def create_freezer(app):
    """Return a Freezer with all route generators registered."""
    config = get_config()
    only_states = config.get('only_states', [])

    freezer = Freezer(app)

    @freezer.register_generator
    def month_page():
        for m in get_upcoming_months():
            yield {'year': m['year'], 'month': m['month']}

    @freezer.register_generator
    def region_page():
        for state in only_states:
            yield {'state': state.lower()}

    @freezer.register_generator
    def week_page():
        for week_id in get_upcoming_weeks(12):
            yield {'week_id': week_id}

    @freezer.register_generator
    def locations_index():
        if only_states:
            yield {}

    @freezer.register_generator
    def approved_groups_list():
        yield {}

    @freezer.register_generator
    def virtual_events_page():
        yield {}

    @freezer.register_generator
    def category_page():
        for slug in get_categories().keys():
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
    def events_rss_feed():
        yield {}

    @freezer.register_generator
    def category_ical_feed():
        for slug in get_categories().keys():
            yield {'slug': slug}

    @freezer.register_generator
    def location_ical_feed():
        for state in only_states:
            yield {'state': state.lower()}

    @freezer.register_generator
    def category_rss_feed():
        for slug in get_categories().keys():
            yield {'slug': slug}

    @freezer.register_generator
    def location_rss_feed():
        for state in only_states:
            yield {'state': state.lower()}

    @freezer.register_generator
    def not_found_page():
        yield {}

    return freezer


def main(site_dir=None, output_dir=None):
    if site_dir is None:
        site_dir = os.getcwd()
    site_dir = os.path.abspath(site_dir)

    if output_dir is None:
        output_dir = os.path.join(site_dir, 'build')

    app = create_app(site_dir)
    app.config['FREEZER_DESTINATION'] = output_dir
    app.config['FREEZER_RELATIVE_URLS'] = True

    os.makedirs(output_dir, exist_ok=True)

    freezer = create_freezer(app)
    freezer.freeze()

    import shutil
    categories_src = os.path.join(site_dir, 'static', 'categories.json')
    categories_dst = os.path.join(output_dir, 'static', 'categories.json')
    if os.path.exists(categories_src):
        shutil.copy2(categories_src, categories_dst)

    print(f"Generated static site to {output_dir}")


if __name__ == '__main__':
    main()
