"""
Public API routes (no authentication required).
"""

import json

from db import get_events_by_date, get_all_overrides, get_all_categories


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

    events = get_events_by_date(date_prefix)
    events.sort(key=lambda x: (
        str(x.get('date', '')),
        str(x.get('time', '')),
    ))

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps(events),
    }


def get_overrides(event, jinja_env):
    """GET /api/overrides — returns JSON list of overrides."""
    overrides = get_all_overrides()

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps(overrides),
    }


def upcoming_ics(event, jinja_env):
    """GET /api/events/upcoming.ics — placeholder for iCal feed."""
    return {
        'statusCode': 501,
        'headers': {'Content-Type': 'text/plain'},
        'body': 'iCal feed not yet implemented via API',
    }
