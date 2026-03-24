"""
Public API routes (no authentication required).
"""

import json

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
