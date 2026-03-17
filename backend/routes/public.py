"""
Public API routes (no authentication required).
"""

import json

from db import get_all_events, get_all_categories
from icalendar import Calendar, Event as ICalEvent
from datetime import datetime, date, time, timedelta
import pytz

local_tz = pytz.timezone('US/Eastern')


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


def upcoming_ics(event, jinja_env):
    """GET /api/events/upcoming.ics — returns iCal feed of all events."""
    all_events = get_all_events()
    
    cal = Calendar()
    cal.add('prodid', '-//dctech.events//mxm.dk//')
    cal.add('version', '2.0')
    
    for event_data in all_events:
        guid = event_data.get('guid') or event_data.get('eventId')
        if not guid:
            continue
            
        if event_data.get('hidden'):
            continue
            
        evt = ICalEvent()
        
        title = event_data.get('title', 'Untitled Event')
        evt.add('summary', title)
        
        # Date/Time handling
        evt_date_str = event_data.get('date')
        evt_time_str = event_data.get('time') or '00:00'
        
        if evt_date_str:
            try:
                dt_naive = datetime.strptime(f"{evt_date_str} {evt_time_str}", "%Y-%m-%d %H:%M")
                dt = local_tz.localize(dt_naive)
                evt.add('dtstart', dt)
                # Default duration 1 hour if not specified
                evt.add('dtend', dt + timedelta(hours=1))
            except ValueError:
                try:
                    d = datetime.strptime(evt_date_str, "%Y-%m-%d").date()
                    evt.add('dtstart', d)
                except ValueError:
                    continue
        
        evt.add('uid', guid)
        
        url = event_data.get('url')
        if url:
            evt.add('url', url)
            
        location = event_data.get('location')
        if location:
            evt.add('location', location)
            
        description = event_data.get('description', '')
        if description:
            evt.add('description', description)
            
        # Add categories
        categories = event_data.get('categories', [])
        if categories:
            evt.add('categories', categories)
            
        cal.add_component(evt)
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/calendar; charset=utf-8',
            'Content-Disposition': 'attachment; filename="upcoming.ics"'
        },
        'body': cal.to_ical().decode('utf-8'),
    }
