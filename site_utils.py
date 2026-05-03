#!/usr/bin/env python3
"""
Utility functions for multi-site support.
Provides site-aware directory paths and configuration loading.
"""

import os
import sys
import yaml
from pathlib import Path

# Default sites
SITES = ['dctech', 'dcstem']
DEFAULT_SITE = 'dctech'

def get_site_from_args(default=DEFAULT_SITE):
    """
    Extract site name from command line arguments.
    Supports: --site dctech, --site dcstem, --all-sites
    """
    if '--all-sites' in sys.argv:
        return SITES
    
    if '--site' in sys.argv:
        idx = sys.argv.index('--site')
        if idx + 1 < len(sys.argv):
            site = sys.argv[idx + 1]
            if site in SITES:
                return [site]
            else:
                raise ValueError(f"Invalid site: {site}. Must be one of {SITES}")
    
    return [default]

def get_groups_dir(site):
    """Get the groups directory for a specific site."""
    return os.path.join(site, '_groups')

def get_single_events_dir(site):
    """Get the single events directory for a specific site."""
    return os.path.join(site, '_single_events')

def get_recurring_events_dir(site):
    """Get the recurring events directory for a specific site."""
    return os.path.join(site, '_recurring_events')

def get_categories_dir(site):
    """Get the categories directory for a specific site."""
    return os.path.join(site, '_categories')

def get_event_overrides_dir(site):
    """Get the event overrides directory for a specific site."""
    return os.path.join(site, '_event_overrides')

def get_data_dir(site):
    """Get the data directory for a specific site (generated files)."""
    return os.path.join('_data', site)

def get_cache_dir(site):
    """Get the cache directory for a specific site."""
    return os.path.join('_cache', site)

def get_config_file(site):
    """Get the config file for a specific site."""
    config_file = f'config.{site}.yaml'
    if not os.path.exists(config_file):
        # Fall back to default config.yaml if site-specific doesn't exist
        return 'config.yaml'
    return config_file

def load_site_config(site):
    """Load configuration for a specific site."""
    config_file = get_config_file(site)
    config = {}
    
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f) or {}
    
    # Ensure data_dir is set
    if 'data_dir' not in config:
        config['data_dir'] = site
    
    return config

def ensure_site_directories(site):
    """Ensure all necessary directories exist for a site."""
    dirs = [
        get_groups_dir(site),
        get_single_events_dir(site),
        get_recurring_events_dir(site),
        get_categories_dir(site),
        get_event_overrides_dir(site),
        get_data_dir(site),
        get_cache_dir(site),
        os.path.join(get_cache_dir(site), 'ical'),
        os.path.join(get_cache_dir(site), 'json-ld'),
    ]
    
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
