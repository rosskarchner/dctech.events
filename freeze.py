#!/usr/bin/env python3
from flask_frozen import Freezer
from flask import g
import os
import sys
from datetime import datetime, timedelta

# Import app
from app import app
from app import local_tz, get_events, get_upcoming_weeks, get_categories, get_upcoming_months
from site_utils import load_site_config

def create_freezer_with_generators(app_instance, site='dctech'):
    """Create a freezer with all route generators registered"""
    freezer = Freezer(app_instance)
    
    @freezer.register_generator
    def month_page():
        """Generate URLs for month pages"""
        months = get_upcoming_months()
        for month_data in months:
            yield {'site': site, 'year': month_data['year'], 'month': month_data['month']}

    @freezer.register_generator
    def region_page():
        """Generate URLs for region pages"""
        yield {'site': site, 'state': 'dc'}
        yield {'site': site, 'state': 'va'}
        yield {'site': site, 'state': 'md'}

    @freezer.register_generator
    def week_page():
        """Generate URLs for week pages"""
        # Generate pages for 12 weeks ahead
        for week_id in get_upcoming_weeks(12):
            yield {'site': site, 'week_id': week_id}

    @freezer.register_generator
    def locations_index():
        """Generate the locations index page"""
        yield {'site': site}

    @freezer.register_generator
    def approved_groups_list():
        """Generate the groups page"""
        yield {'site': site}

    @freezer.register_generator
    def virtual_events_page():
        """Generate the virtual events page"""
        yield {'site': site}

    @freezer.register_generator
    def category_page():
        """Generate URLs for individual category pages"""
        categories = get_categories()
        for slug in categories.keys():
            yield {'site': site, 'slug': slug}

    @freezer.register_generator
    def feeds_page():
        """Generate the feeds listing page"""
        yield {'site': site}

    @freezer.register_generator
    def newsletter_html():
        """Generate the HTML newsletter page"""
        yield {'site': site}

    @freezer.register_generator
    def newsletter_text():
        """Generate the text newsletter page"""
        yield {'site': site}

    @freezer.register_generator
    def sitemap():
        """Generate the sitemap.xml page"""
        yield {'site': site}

    @freezer.register_generator
    def events_json():
        """Generate the events JSON file"""
        yield {'site': site}

    @freezer.register_generator
    def ical_feed():
        """Generate the iCal feed"""
        yield {'site': site}

    @freezer.register_generator
    def category_ical_feed():
        """Generate iCal feeds for each category"""
        categories = get_categories()
        for slug in categories.keys():
            yield {'site': site, 'slug': slug}

    @freezer.register_generator
    def location_ical_feed():
        """Generate iCal feeds for each location"""
        yield {'site': site, 'state': 'dc'}
        yield {'site': site, 'state': 'va'}
        yield {'site': site, 'state': 'md'}

    @freezer.register_generator
    def category_rss_feed():
        """Generate RSS feeds for each category"""
        categories = get_categories()
        for slug in categories.keys():
            yield {'site': site, 'slug': slug}

    @freezer.register_generator
    def location_rss_feed():
        """Generate RSS feeds for each location"""
        yield {'site': site, 'state': 'dc'}
        yield {'site': site, 'state': 'va'}
        yield {'site': site, 'state': 'md'}

    @freezer.register_generator
    def not_found_page():
        """Generate the 404 error page"""
        yield {'site': site}
    
    return freezer

def freeze_site(site):
    """Freeze a specific site to its build directory"""
    output_dir = f'build/{site}'
    app.config['FREEZER_DESTINATION'] = output_dir
    app.config['FREEZER_RELATIVE_URLS'] = True
    app.config['FREEZING_SITE'] = site  # Set the current freezing site globally
    
    print(f"\n{'='*60}")
    print(f"Freezing {site.upper()} to {output_dir}")
    print(f"{'='*60}")
    
    try:
        os.makedirs('build', exist_ok=True)
        
        # Create a new app instance for this site to avoid state pollution
        from app import app as base_app
        from flask import Flask
        
        # Use a custom before_request handler on the base app
        # that will be active during freeze
        with app.app_context():
            g.site = site
            g.site_config = load_site_config(site)
            
            # Create freezer and freeze
            freezer = create_freezer_with_generators(app, site)
            freezer.freeze()
        
        print(f"✅ Successfully generated {site} to {output_dir}")
        return True
    except Exception as e:
        print(f"❌ Error freezing {site}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up the freezing flag
        if 'FREEZING_SITE' in app.config:
            del app.config['FREEZING_SITE']

if __name__ == '__main__':
    # Parse arguments directly
    site = None
    if len(sys.argv) > 1:
        if sys.argv[1] == '--site' and len(sys.argv) > 2:
            site = sys.argv[2]
        else:
            site = sys.argv[1]
    
    if site and site in ['dctech', 'dcstem']:
        # Freeze specific site
        success = freeze_site(site)
        sys.exit(0 if success else 1)
    
    elif site == 'all' or not site:
        # Freeze all sites
        print(f"\n{'='*60}")
        print("🚀 MULTI-SITE STATIC GENERATION")
        print(f"{'='*60}")
        
        results = {}
        for site_name in ['dctech', 'dcstem']:
            # Reload app to clear state between sites
            import importlib
            import app as app_module
            importlib.reload(app_module)
            
            results[site_name] = freeze_site(site_name)
        
        print(f"\n{'='*60}")
        print("RESULTS:")
        print(f"{'='*60}")
        for site_name, success in results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{site_name:20} {status}")
        
        all_success = all(results.values())
        if all_success:
            print(f"\n✅ All sites successfully frozen!")
        else:
            print(f"\n❌ Some sites failed to freeze")
        
        sys.exit(0 if all_success else 1)
    
    else:
        print(f"Invalid site: {site}")
        print("Usage: python freeze.py [--site dctech|dcstem|all]")
        sys.exit(1)
