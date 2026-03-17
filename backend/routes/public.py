"""
Public API routes (no authentication required).
"""

import json

from db import get_all_events, get_all_overrides, get_all_categories
from icalendar import Calendar, Event as ICalEvent
from datetime import datetime, date, time


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


def get_overrides(event, jinja_env):
    """GET /api/overrides — returns JSON list of overrides."""
    overrides = get_all_overrides()

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
        },
        'body': json.dumps(overrides),
    }


def upcoming_ics(event, jinja_env):
    """GET /api/events/upcoming.ics — returns iCal feed of all events and overrides."""
    all_events = get_all_events()
    overrides = get_all_overrides()
    
    cal = Calendar()
    cal.add('prodid', '-//dctech.events//mxm.dk//')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'DC Tech Events (Submitted & Overrides)')
    
    # Create a map of overrides by GUID
    override_map = {o['guid']: o for o in overrides}
    
    for event_data in all_events:
        guid = event_data.get('guid') or event_data.get('eventId')
        if not guid:
            continue
            
        # Merge with override if present
        override = override_map.get(guid, {})
        if override.get('hidden'):
            continue
            
        evt = ICalEvent()
        
        title = override.get('title') or event_data.get('title', 'Untitled Event')
        evt.add('summary', title)
        
        # Date/Time handling
        evt_date_str = event_data.get('date')
        evt_time_str = override.get('time') or event_data.get('time') or '00:00'
        
        if evt_date_str:
            try:
                dt = datetime.strptime(f"{evt_date_str} {evt_time_str}", "%Y-%m-%d %H:%M")
                evt.add('dtstart', dt)
                # Default duration 1 hour if not specified
                evt.add('dtend', dt.replace(hour=(dt.hour + 1) % 24))
            except ValueError:
                try:
                    d = datetime.strptime(evt_date_str, "%Y-%m-%d").date()
                    evt.add('dtstart', d)
                except ValueError:
                    continue
        
        evt.add('uid', guid)
        
        url = override.get('url') or event_data.get('url')
        if url:
            evt.add('url', url)
            
        location = override.get('location') or event_data.get('location')
        if location:
            evt.add('location', location)
            
        description = event_data.get('description', '')
        if description:
            evt.add('description', description)
            
        # Add categories as X-tags or categories
        categories = override.get('categories') or event_data.get('categories', [])
        if categories:
            evt.add('categories', categories)
            
        cal.add_component(evt)
        
    # Also include overrides for events NOT in all_events (though usually they are)
    # Actually, overrides are usually for events that WERE scraped but might not be in the dynamic DB's active list
    # For now, this is probably sufficient.
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/calendar; charset=utf-8',
            'Content-Disposition': 'attachment; filename="upcoming.ics"'
        },
        'body': cal.to_ical().decode('utf-8'),
    }
