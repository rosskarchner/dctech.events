"""
Public API routes (no authentication required).
"""

import json
import os
import yaml

from db import get_all_events, get_all_categories


def health(event, jinja_env):
    """GET /health"""
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'status': 'ok'}),
    }


def get_events(event, jinja_env):
    """GET /api/events — returns JSON list of events."""
    params = event.get('queryStringParameters') or {}
    date_prefix = params.get('date')

    all_events = get_all_events(date_prefix)
    
    # Filter out hidden and duplicate events
    events = [e for e in all_events if not e.get('hidden') and not e.get('duplicate_of')]
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
        },
        'body': json.dumps(events),
    }


def get_categories(event, jinja_env):
    """GET /api/categories — returns JSON map of categories.
    
    Supports query parameter:
    - site: 'dctech' or 'dcstem' (defaults to 'dctech')
    """
    params = event.get('queryStringParameters') or {}
    site = params.get('site', 'dctech')
    
    # Load categories from YAML files
    categories = {}
    categories_dir = f'{site}/_categories'
    
    if os.path.exists(categories_dir):
        for filename in os.listdir(categories_dir):
            if filename.endswith('.yaml'):
                slug = filename[:-5]  # Remove .yaml extension
                try:
                    with open(os.path.join(categories_dir, filename), 'r') as f:
                        cat_data = yaml.safe_load(f) or {}
                        categories[slug] = {
                            'slug': slug,
                            'name': cat_data.get('name', slug),
                            'description': cat_data.get('description', ''),
                        }
                except Exception as e:
                    print(f'Error loading category {slug}: {e}')
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
        },
        'body': json.dumps(categories),
    }
