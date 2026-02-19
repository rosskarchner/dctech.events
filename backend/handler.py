"""
Lambda handler for the DC Tech Events API.

Lightweight router that dispatches to route modules.
Returns HTML fragments for HTMX endpoints, JSON for public API.
"""

import json
import os
import traceback

from jinja2 import Environment, FileSystemLoader

from routes import public, submit, admin

# Set up Jinja2 template environment
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=True,
)


# List of allowed origins for CORS
ALLOWED_ORIGINS = [
    'https://suggest.dctech.events',
    'https://manage.dctech.events',
    'https://dctech.events',
]


def get_cors_origin(event):
    """Get the appropriate CORS origin header based on request origin."""
    request_origin = event.get('headers', {}).get('Origin', '') or event.get('headers', {}).get('origin', '')
    if request_origin in ALLOWED_ORIGINS:
        return request_origin
    # Fallback to wildcard for public endpoints (will be restricted below)
    return '*'


def html_response(status_code, body, headers=None, allow_all_origins=False):
    """Build an HTML response.
    
    Args:
        status_code: HTTP status code
        body: Response body
        headers: Additional headers to include
        allow_all_origins: If False (default), restrict to ALLOWED_ORIGINS
    """
    resp_headers = {
        'Content-Type': 'text/html; charset=utf-8',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization,HX-Request,HX-Trigger,HX-Trigger-Name,HX-Target,HX-Current-URL',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
    }
    if headers:
        resp_headers.update(headers)
    return {
        'statusCode': status_code,
        'headers': resp_headers,
        'body': body,
    }


def json_response(status_code, body, allow_all_origins=False):
    """Build a JSON response.
    
    Args:
        status_code: HTTP status code
        body: Response body
        allow_all_origins: If False (default), restrict to ALLOWED_ORIGINS
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization,HX-Request,HX-Trigger,HX-Trigger-Name,HX-Target,HX-Current-URL',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
        },
        'body': json.dumps(body) if isinstance(body, (dict, list)) else body,
    }


def lambda_handler(event, context):
    """Main Lambda entry point."""
    http_method = event.get('httpMethod', 'GET')
    path = event.get('path', '/')
    resource = event.get('resource', path)

    # Determine CORS origin based on request
    cors_origin = get_cors_origin(event)

    # Handle CORS preflight
    if http_method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': cors_origin,
                'Access-Control-Allow-Headers': 'Content-Type,Authorization,HX-Request,HX-Trigger,HX-Trigger-Name,HX-Target,HX-Current-URL',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
            },
            'body': json.dumps({'message': 'ok'}),
        }

    # Add CORS origin to all responses
    def add_cors(response):
        if 'headers' not in response:
            response['headers'] = {}
        response['headers']['Access-Control-Allow-Origin'] = cors_origin
        return response

    try:
        # Public routes
        if path == '/health':
            return add_cors(public.health(event, jinja_env))

        if path == '/api/events':
            return add_cors(public.get_events(event, jinja_env))

        if path == '/api/overrides':
            return add_cors(public.get_overrides(event, jinja_env))

        if path.startswith('/api/events/upcoming.ics'):
            return add_cors(public.upcoming_ics(event, jinja_env))

        # Submission routes (authenticated)
        if path == '/submit' and http_method == 'GET':
            return add_cors(submit.submit_form(event, jinja_env))
        if path == '/submit' and http_method == 'POST':
            return add_cors(submit.submit_event(event, jinja_env))

        if path == '/my-submissions' and http_method == 'GET':
            return add_cors(submit.my_submissions(event, jinja_env))

        # Admin routes (authenticated + admin group)
        if path == '/admin' and http_method == 'GET':
            return add_cors(admin.dashboard(event, jinja_env))

        if path == '/admin/queue' and http_method == 'GET':
            return add_cors(admin.get_queue(event, jinja_env))

        if path.startswith('/admin/draft/') and path.endswith('/approve') and http_method == 'POST':
            draft_id = path.split('/')[3]
            return add_cors(admin.approve_draft(event, jinja_env, draft_id))

        if path.startswith('/admin/draft/') and path.endswith('/approve-form') and http_method == 'GET':
            draft_id = path.split('/')[3]
            return add_cors(admin.get_approve_form(event, jinja_env, draft_id))

        if path.startswith('/admin/draft/') and path.endswith('/row') and http_method == 'GET':
            draft_id = path.split('/')[3]
            return add_cors(admin.get_draft_row(event, jinja_env, draft_id))

        if path.startswith('/admin/draft/') and path.endswith('/reject') and http_method == 'POST':
            draft_id = path.split('/')[3]
            return add_cors(admin.reject_draft(event, jinja_env, draft_id))

        if path.startswith('/admin/draft/') and http_method == 'GET':
            draft_id = path.split('/')[3]
            return add_cors(admin.get_draft(event, jinja_env, draft_id))

        if path == '/admin/groups' and http_method == 'GET':
            return add_cors(admin.get_groups(event, jinja_env))

        if path.startswith('/admin/groups/') and path.endswith('/edit') and http_method == 'GET':
            slug = path.split('/')[3]
            return add_cors(admin.edit_group_form(event, jinja_env, slug))

        if path.startswith('/admin/groups/') and http_method == 'PUT':
            slug = path.split('/')[3]
            return add_cors(admin.update_group(event, jinja_env, slug))

        if path == '/admin/events' and http_method == 'GET':
            return add_cors(admin.get_events(event, jinja_env))

        if path == '/admin/events/bulk' and http_method == 'POST':
            return add_cors(admin.handle_bulk_action(event, jinja_env))

        if resource == '/admin/events/{guid}/edit' and http_method == 'GET':
            guid = event.get('pathParameters', {}).get('guid', '')
            return add_cors(admin.get_event_edit_form(event, jinja_env, guid))

        if resource == '/admin/events/{guid}' and http_method == 'PUT':
            guid = event.get('pathParameters', {}).get('guid', '')
            return add_cors(admin.save_event_edit(event, jinja_env, guid))

        if path == '/admin/overrides' and http_method == 'GET':
            return add_cors(admin.get_overrides(event, jinja_env))

        if path == '/admin/overrides' and http_method == 'POST':
            return add_cors(admin.create_override(event, jinja_env))

        if path.startswith('/admin/overrides/') and http_method == 'DELETE':
            guid = path.split('/')[3]
            return add_cors(admin.delete_override(event, jinja_env))

        return add_cors(json_response(404, {'error': 'Not found'}))

    except Exception as e:
        print(f"Error handling {http_method} {path}: {traceback.format_exc()}")
        return add_cors(json_response(500, {'error': 'Internal server error'}))
