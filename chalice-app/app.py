"""
DC Tech Events - Chalice API Application
"""
import os
import json
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional

from chalice import Chalice, Response
import pytz

from chalicelib.dynamodb import EventsDatabase
from chalicelib.event_utils import (
    prepare_events_by_day,
    filter_events_by_location,
    filter_events_by_week,
    get_week_identifier,
    is_virtual_event,
)
from chalicelib.groups import GroupsManager
from chalicelib.ical_export import generate_ical_feed

# Initialize Chalice app
app = Chalice(app_name='dctech-events')
app.debug = os.getenv('ENVIRONMENT') != 'prod'

# Configuration
TIMEZONE_NAME = os.getenv('TIMEZONE', 'US/Eastern')
SITE_NAME = os.getenv('SITE_NAME', 'DC Tech Events')
TAGLINE = os.getenv('TAGLINE', 'Technology conferences and meetups in and around Washington, DC')
BASE_URL = os.getenv('BASE_URL', 'https://dctech.events')

local_tz = pytz.timezone(TIMEZONE_NAME)

# Initialize database and groups manager
db = EventsDatabase(
    table_name=os.getenv('DYNAMODB_TABLE_NAME'),
    region=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
)

groups_manager = GroupsManager(
    bucket_name=os.getenv('ASSETS_BUCKET'),
    region=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
)


# Helper function to get upcoming events
def get_upcoming_events(
    days_ahead: int = 90,
    location_type: Optional[str] = None,
    state: Optional[str] = None,
    group_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get upcoming events from DynamoDB"""
    start_date = datetime.now(local_tz).date()
    end_date = start_date + timedelta(days=days_ahead)

    # Determine which query method to use based on filters
    if group_id:
        events = db.get_events_by_group(
            group_id=group_id,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat()
        )
    elif location_type:
        events = db.get_events_by_location_type(
            location_type=location_type,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat()
        )
    elif state:
        events = db.get_events_by_state(
            state=state,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat()
        )
    else:
        # Get all events (state='ALL')
        events = db.get_events_by_state(
            state='ALL',
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat()
        )

    return events


def render_json(data: Dict[str, Any], status_code: int = 200) -> Response:
    """Helper to render JSON response"""
    return Response(
        body=json.dumps(data, default=str),
        status_code=status_code,
        headers={'Content-Type': 'application/json'}
    )


def render_html(template_name: str, context: Dict[str, Any]) -> Response:
    """
    Render HTML template
    Note: For production, consider using a template engine or returning JSON
    and building a separate frontend (React, Vue, etc.)
    """
    # For now, return JSON with a note about template rendering
    # In a full implementation, you would use Jinja2 or similar
    return render_json({
        'template': template_name,
        'context': context,
        'note': 'HTML rendering not implemented in serverless version. Use /api/* endpoints for JSON data.'
    })


# =============================================================================
# API Routes
# =============================================================================

@app.route('/api/events', methods=['GET'], cors=True)
def api_get_events():
    """
    Get events as JSON

    Query parameters:
    - state: Filter by state (DC, MD, VA)
    - location_type: Filter by location type (virtual, in_person)
    - group_id: Filter by group ID
    - start_date: Filter events after this date (YYYY-MM-DD)
    - end_date: Filter events before this date (YYYY-MM-DD)
    - limit: Maximum number of events to return (default: 100)
    """
    params = app.current_request.query_params or {}

    state = params.get('state')
    location_type = params.get('location_type')
    group_id = params.get('group_id')
    limit = int(params.get('limit', 100))

    # Get events
    events = get_upcoming_events(
        days_ahead=90,
        location_type=location_type,
        state=state,
        group_id=group_id
    )

    # Apply limit
    events = events[:limit]

    return render_json({
        'events': events,
        'count': len(events),
        'filters': {
            'state': state,
            'location_type': location_type,
            'group_id': group_id,
        }
    })


@app.route('/api/events/upcoming', methods=['GET'], cors=True)
def api_upcoming_events():
    """Get upcoming in-person events organized by day"""
    # Get in-person events only
    events = get_upcoming_events(
        days_ahead=90,
        location_type='in_person'
    )

    # Organize by day
    days_data = prepare_events_by_day(events, local_tz)

    return render_json({
        'days': days_data,
        'count': len(events),
        'location_type': 'in_person'
    })


@app.route('/api/events/virtual', methods=['GET'], cors=True)
def api_virtual_events():
    """Get upcoming virtual events organized by day"""
    events = get_upcoming_events(
        days_ahead=90,
        location_type='virtual'
    )

    days_data = prepare_events_by_day(events, local_tz)

    return render_json({
        'days': days_data,
        'count': len(events),
        'location_type': 'virtual'
    })


@app.route('/api/events/week/{week_id}', methods=['GET'], cors=True)
def api_week_events(week_id):
    """
    Get events for a specific week

    week_id format: YYYY-Www (e.g., 2026-W02)
    """
    # Get all events
    events = get_upcoming_events(days_ahead=365)

    # Filter by week
    week_events = filter_events_by_week(events, week_id)

    # Organize by day
    days_data = prepare_events_by_day(week_events, local_tz)

    return render_json({
        'week_id': week_id,
        'days': days_data,
        'count': len(week_events)
    })


@app.route('/api/locations', methods=['GET'], cors=True)
def api_locations():
    """Get event counts by location (state/city)"""
    # Get all upcoming events
    events = get_upcoming_events(days_ahead=90)

    # Count by state
    state_counts = {}
    for event in events:
        state = event.get('state', 'Unknown')
        state_counts[state] = state_counts.get(state, 0) + 1

    return render_json({
        'states': state_counts,
        'total': len(events)
    })


@app.route('/api/locations/{state}', methods=['GET'], cors=True)
def api_state_events(state):
    """Get events for a specific state"""
    state = state.upper()

    if state not in ['DC', 'MD', 'VA']:
        return render_json({'error': 'Invalid state. Must be DC, MD, or VA'}, 400)

    events = get_upcoming_events(
        days_ahead=90,
        state=state
    )

    days_data = prepare_events_by_day(events, local_tz)

    return render_json({
        'state': state,
        'days': days_data,
        'count': len(events)
    })


@app.route('/api/groups', methods=['GET'], cors=True)
def api_groups():
    """Get all approved groups"""
    groups = groups_manager.get_all_groups()

    # Filter to only active groups
    active_groups = [g for g in groups if g.get('active', False)]

    # Sort by name
    active_groups.sort(key=lambda x: x.get('name', '').lower())

    return render_json({
        'groups': active_groups,
        'count': len(active_groups)
    })


@app.route('/api/groups/{group_id}', methods=['GET'], cors=True)
def api_group_events(group_id):
    """Get events for a specific group"""
    events = get_upcoming_events(
        days_ahead=365,
        group_id=group_id
    )

    days_data = prepare_events_by_day(events, local_tz)

    # Get group info
    group = groups_manager.get_group(group_id)

    return render_json({
        'group': group,
        'days': days_data,
        'count': len(events)
    })


@app.route('/events.ics', methods=['GET'])
def ical_feed():
    """Generate iCal feed of all upcoming events"""
    events = get_upcoming_events(days_ahead=90)

    ical_content = generate_ical_feed(
        events=events,
        site_name=SITE_NAME,
        base_url=BASE_URL,
        timezone=local_tz
    )

    return Response(
        body=ical_content,
        status_code=200,
        headers={
            'Content-Type': 'text/calendar; charset=utf-8',
            'Content-Disposition': 'attachment; filename="dctech-events.ics"'
        }
    )


@app.route('/sitemap.xml', methods=['GET'])
def sitemap():
    """Generate sitemap.xml"""
    # Get unique week IDs
    events = get_upcoming_events(days_ahead=365)
    week_ids = set()
    for event in events:
        week_id = get_week_identifier(event.get('start_datetime', ''))
        if week_id:
            week_ids.add(week_id)

    # Build sitemap
    urls = [
        {'loc': BASE_URL + '/', 'priority': '1.0'},
        {'loc': BASE_URL + '/virtual/', 'priority': '0.9'},
        {'loc': BASE_URL + '/locations/', 'priority': '0.8'},
        {'loc': BASE_URL + '/groups/', 'priority': '0.8'},
    ]

    # Add state pages
    for state in ['DC', 'MD', 'VA']:
        urls.append({
            'loc': f"{BASE_URL}/locations/{state}/",
            'priority': '0.7'
        })

    # Add week pages
    for week_id in sorted(week_ids)[:52]:  # Limit to next 52 weeks
        urls.append({
            'loc': f"{BASE_URL}/week/{week_id}/",
            'priority': '0.6'
        })

    # Generate XML
    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    for url in urls:
        xml_lines.append('  <url>')
        xml_lines.append(f'    <loc>{url["loc"]}</loc>')
        xml_lines.append(f'    <priority>{url["priority"]}</priority>')
        xml_lines.append('  </url>')

    xml_lines.append('</urlset>')

    return Response(
        body='\n'.join(xml_lines),
        status_code=200,
        headers={'Content-Type': 'application/xml'}
    )


# =============================================================================
# Legacy Routes (for backward compatibility - return HTML or redirect to API)
# =============================================================================

@app.route('/', methods=['GET'])
def index():
    """Homepage - upcoming in-person events"""
    # For serverless, redirect to API or return JSON
    # In production, you'd serve a static frontend from S3/CloudFront
    return render_html('index.html', {
        'api_endpoint': '/api/events/upcoming',
        'message': 'Use /api/events/upcoming for JSON data'
    })


@app.route('/virtual/', methods=['GET'])
def virtual():
    """Virtual events page"""
    return render_html('virtual.html', {
        'api_endpoint': '/api/events/virtual',
        'message': 'Use /api/events/virtual for JSON data'
    })


@app.route('/week/{week_id}/', methods=['GET'])
def week_page(week_id):
    """Week events page"""
    return render_html('week.html', {
        'api_endpoint': f'/api/events/week/{week_id}',
        'week_id': week_id,
        'message': f'Use /api/events/week/{week_id} for JSON data'
    })


@app.route('/locations/', methods=['GET'])
def locations():
    """Locations page"""
    return render_html('locations.html', {
        'api_endpoint': '/api/locations',
        'message': 'Use /api/locations for JSON data'
    })


@app.route('/locations/{state}/', methods=['GET'])
def state_page(state):
    """State events page"""
    return render_html('location.html', {
        'api_endpoint': f'/api/locations/{state}',
        'state': state,
        'message': f'Use /api/locations/{state} for JSON data'
    })


@app.route('/groups/', methods=['GET'])
def groups():
    """Groups page"""
    return render_html('groups.html', {
        'api_endpoint': '/api/groups',
        'message': 'Use /api/groups for JSON data'
    })


# Health check
@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return render_json({
        'status': 'healthy',
        'timestamp': datetime.now(local_tz).isoformat(),
        'environment': os.getenv('ENVIRONMENT', 'unknown')
    })
