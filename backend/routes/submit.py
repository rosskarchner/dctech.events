"""
Submission routes (authenticated users).
"""

import json

from auth import get_user_from_event
from db import create_draft, get_all_categories, get_drafts_by_submitter


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

    from datetime import datetime, timedelta
    tomorrow = datetime.now() + timedelta(days=1)
    default_date = tomorrow.strftime('%Y-%m-%d')

    categories = get_all_categories()
    template = jinja_env.get_template('partials/submit_form.html')
    html = template.render(
        categories=categories,
        user_email=claims.get('email', ''),
        default_date=default_date,
        default_hour='6',
        default_minute='30',
        default_ampm='PM',
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
    """POST /submit — create a draft event or group submission."""
    claims, err = get_user_from_event(event)
    if err:
        return err

    data = _parse_body(event)
    submitter = claims.get('email', 'unknown')
    submission_type = data.get('type', 'event')

    if submission_type == 'group':
        return _submit_group(data, submitter, jinja_env)
    return _submit_event(data, submitter, jinja_env)


def _submit_event(data, submitter, jinja_env):
    """Handle event submission."""
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

    # Build time string from hour/minute/ampm fields
    timing = data.get('timing', 'specific')
    time_str = ''
    if timing == 'specific':
        hour = data.get('time_hour', '')
        minute = data.get('time_minute', '')
        ampm = data.get('time_ampm', '')
        if hour and minute and ampm:
            time_str = f'{hour}:{minute} {ampm}'

    draft_data = {
        'title': title,
        'date': date_val,
        'time': time_str,
        'url': data.get('url', ''),
        'city': data.get('city', ''),
        'state': data.get('state', ''),
        'cost': data.get('cost', ''),
        'end_date': data.get('end_date', ''),
        'all_day': timing == 'allday',
    }

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


def _submit_group(data, submitter, jinja_env):
    """Handle group submission."""
    name = data.get('name', '').strip()
    website = data.get('website', '').strip()
    if not name or not website:
        template = jinja_env.get_template('partials/submit_error.html')
        html = template.render(error='Group name and website are required.')
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'text/html; charset=utf-8'},
            'body': html,
        }

    draft_data = {
        'name': name,
        'website': website,
        'ical_url': data.get('ical_url', ''),
        'fallback_url': data.get('fallback_url', ''),
    }

    draft_id = create_draft('group', draft_data, submitter)

    template = jinja_env.get_template('partials/submit_confirmation.html')
    html = template.render(draft_id=draft_id, draft_type='group')

    return {
        'statusCode': 201,
        'headers': {
            'Content-Type': 'text/html; charset=utf-8',
            'Access-Control-Allow-Origin': '*',
        },
        'body': html,
    }


def my_submissions(event, jinja_env):
    """GET /my-submissions — list user's own submissions."""
    claims, err = get_user_from_event(event)
    if err:
        return err

    submitter = claims.get('email', '')
    drafts = get_drafts_by_submitter(submitter)

    template = jinja_env.get_template('partials/my_submissions.html')
    html = template.render(submissions=drafts)

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/html; charset=utf-8',
            'Access-Control-Allow-Origin': '*',
        },
        'body': html,
    }
