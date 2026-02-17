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


def html_response(status_code, body, headers=None):
    """Build an HTML response."""
    resp_headers = {
        'Content-Type': 'text/html; charset=utf-8',
        'Access-Control-Allow-Origin': '*',
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


def json_response(status_code, body):
    """Build a JSON response."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
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

    # Handle CORS preflight
    if http_method == 'OPTIONS':
        return json_response(200, {'message': 'ok'})

    try:
        # Public routes
        if path == '/health':
            return public.health(event, jinja_env)

        if path == '/api/events':
            return public.get_events(event, jinja_env)

        if path == '/api/overrides':
            return public.get_overrides(event, jinja_env)

        if path.startswith('/api/events/upcoming.ics'):
            return public.upcoming_ics(event, jinja_env)

        # Submission routes (authenticated)
        if path == '/submit' and http_method == 'GET':
            return submit.submit_form(event, jinja_env)
        if path == '/submit' and http_method == 'POST':
            return submit.submit_event(event, jinja_env)

        # Admin routes (authenticated + admin group)
        if path == '/admin' and http_method == 'GET':
            return admin.dashboard(event, jinja_env)

        if path == '/admin/queue' and http_method == 'GET':
            return admin.get_queue(event, jinja_env)

        if path.startswith('/admin/draft/') and path.endswith('/approve') and http_method == 'POST':
            draft_id = path.split('/')[3]
            return admin.approve_draft(event, jinja_env, draft_id)

        if path.startswith('/admin/draft/') and path.endswith('/reject') and http_method == 'POST':
            draft_id = path.split('/')[3]
            return admin.reject_draft(event, jinja_env, draft_id)

        if path.startswith('/admin/draft/') and http_method == 'GET':
            draft_id = path.split('/')[3]
            return admin.get_draft(event, jinja_env, draft_id)

        if path == '/admin/groups' and http_method == 'GET':
            return admin.get_groups(event, jinja_env)

        if path.startswith('/admin/groups/') and path.endswith('/edit') and http_method == 'GET':
            slug = path.split('/')[3]
            return admin.edit_group_form(event, jinja_env, slug)

        if path.startswith('/admin/groups/') and http_method == 'PUT':
            slug = path.split('/')[3]
            return admin.update_group(event, jinja_env, slug)

        if path == '/admin/overrides' and http_method == 'GET':
            return admin.get_overrides(event, jinja_env)

        if path == '/admin/overrides' and http_method == 'POST':
            return admin.create_override(event, jinja_env)

        if path.startswith('/admin/overrides/') and http_method == 'DELETE':
            guid = path.split('/')[3]
            return admin.delete_override(event, jinja_env, guid)

        return json_response(404, {'error': 'Not found'})

    except Exception as e:
        print(f"Error handling {http_method} {path}: {traceback.format_exc()}")
        return json_response(500, {'error': 'Internal server error'})
