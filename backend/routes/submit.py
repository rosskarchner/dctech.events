"""
Submission routes (authenticated users).
"""

import json

from auth import get_user_from_event
from db import create_draft, get_all_categories


def _parse_body(event):
    """Parse request body (JSON or form-encoded)."""
    body = event.get('body', '')
    if not body:
        return {}

    content_type = event.get('headers', {}).get('Content-Type', '')
    if not content_type:
        content_type = event.get('headers', {}).get('content-type', '')

    if 'application/json' in content_type:
        return json.loads(body)

    # Form-encoded
    from urllib.parse import parse_qs
    parsed = parse_qs(body)
    return {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}


def submit_form(event, jinja_env):
    """GET /submit — returns the submission form HTML."""
    claims, err = get_user_from_event(event)
    if err:
        return err

    categories = get_all_categories()
    template = jinja_env.get_template('partials/submit_form.html')
    html = template.render(
        categories=categories,
        user_email=claims.get('email', ''),
    )

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/html; charset=utf-8',
            'Access-Control-Allow-Origin': '*',
        },
        'body': html,
    }


def submit_event(event, jinja_env):
    """POST /submit — create a draft event submission."""
    claims, err = get_user_from_event(event)
    if err:
        return err

    data = _parse_body(event)
    submitter = claims.get('email', 'unknown')

    # Validate required fields
    title = data.get('title', '').strip()
    date_val = data.get('date', '').strip()
    if not title or not date_val:
        template = jinja_env.get_template('partials/submit_error.html')
        html = template.render(error='Title and date are required.')
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'text/html; charset=utf-8'},
            'body': html,
        }

    draft_data = {
        'title': title,
        'date': date_val,
        'time': data.get('time', ''),
        'location': data.get('location', ''),
        'url': data.get('url', ''),
        'cost': data.get('cost', ''),
        'description': data.get('description', ''),
        'group_name': data.get('group_name', ''),
    }

    # Handle categories (may be list or comma-separated string)
    categories = data.get('categories', [])
    if isinstance(categories, str):
        categories = [c.strip() for c in categories.split(',') if c.strip()]
    draft_data['categories'] = categories

    draft_id = create_draft('event', draft_data, submitter)

    template = jinja_env.get_template('partials/submit_confirmation.html')
    html = template.render(draft_id=draft_id, draft_type='event')

    return {
        'statusCode': 201,
        'headers': {
            'Content-Type': 'text/html; charset=utf-8',
            'Access-Control-Allow-Origin': '*',
        },
        'body': html,
    }
