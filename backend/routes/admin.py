"""
Admin routes (requires authentication + admins group).

All routes return HTML fragments for HTMX swap.
"""

import json
import boto3

from auth import get_user_from_event, require_admin
from db import (
    get_drafts_by_status, get_draft as db_get_draft, update_draft_status,
    promote_draft_to_event,
    get_all_categories,
)


def _admin_check(event):
    """Validate auth + admin group. Returns (claims, error_response)."""
    claims, err = get_user_from_event(event)
    if err:
        return None, err
    
    admin_err = require_admin(claims)
    if admin_err:
        return None, admin_err
        
    return claims, None


def _html(status_code, body, event=None):
    """Return HTML response."""
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'text/html'},
        'body': body,
    }


def _json(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(body),
    }


def _parse_body(event):
    """Parse application/x-www-form-urlencoded body."""
    from urllib.parse import parse_qs
    body = event.get('body', '')
    parsed = parse_qs(body)
    return {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}


def dashboard(event, jinja_env):
    """GET /admin/dashboard — Main admin view."""
    claims, err = _admin_check(event)
    if err:
        return err

    template = jinja_env.get_template('admin/dashboard.html')
    html = template.render(claims=claims)
    return _html(200, html, event)


# ─── Draft Queue ──────────────────────────────────────────────────

def get_queue(event, jinja_env):
    """GET /admin/queue — Draft review queue."""
    claims, err = _admin_check(event)
    if err:
        return err

    drafts = get_drafts_by_status('pending')
    template = jinja_env.get_template('partials/draft_queue.html')
    html = template.render(drafts=drafts)
    return _html(200, html, event)


def get_draft(event, jinja_env, draft_id):
    """GET /admin/draft/{id} — Draft detail."""
    claims, err = _admin_check(event)
    if err:
        return err

    draft = db_get_draft(draft_id)
    if not draft:
        return {'statusCode': 404, 'body': 'Draft not found'}

    template = jinja_env.get_template('partials/draft_detail.html')
    html = template.render(draft=draft)
    return _html(200, html, event)


def get_approve_form(event, jinja_env, draft_id):
    """GET /admin/draft/{id}/approve-form — Approval form."""
    claims, err = _admin_check(event)
    if err:
        return err

    draft = db_get_draft(draft_id)
    if not draft:
        return {'statusCode': 404, 'body': 'Draft not found'}

    categories = get_all_categories()
    template = jinja_env.get_template('partials/draft_approve_form.html')
    html = template.render(draft=draft, categories=categories)
    return _html(200, html, event)


def get_draft_row(event, jinja_env, draft_id):
    """GET /admin/draft/{id}/row — Return just the queue row."""
    draft = db_get_draft(draft_id)
    template = jinja_env.get_template('partials/draft_row.html')
    html = template.render(draft=draft)
    return _html(200, html)


def approve_draft(event, jinja_env, draft_id):
    """POST /admin/draft/{id}/approve — approve event or group draft."""
    claims, err = _admin_check(event)
    if err:
        return err

    data = _parse_body(event)

    # Normalize categories
    cats = data.get('categories', [])
    if isinstance(cats, str):
        cats = [cats] if cats else []
    data['categories'] = cats

    draft = db_get_draft(draft_id)
    if not draft:
        return {'statusCode': 404, 'body': 'Draft not found'}

    draft_type = draft.get('draft_type', 'event')
    merged = {k: v for k, v in draft.items() if v is not None}
    merged.update({k: v for k, v in data.items() if v is not None})

    # Best-effort: commit YAML to GitHub repo
    commit_url = None
    try:
        if draft_type == 'group':
            from github_commit import commit_group_to_repo
            commit_url = commit_group_to_repo(merged)
        else:
            from github_commit import commit_event_to_repo
            commit_url = commit_event_to_repo(merged)
    except Exception as e:
        print(f"WARNING: GitHub commit failed (non-blocking): {e}")

    update_draft_status(draft_id, 'APPROVED', claims.get('email', ''), commit_url=commit_url)

    label = 'group' if draft_type == 'group' else 'event'
    return _html(200, f"Approved and committed {label} to repo.")


def reject_draft(event, jinja_env, draft_id):
    """POST /admin/draft/{id}/reject."""
    claims, err = _admin_check(event)
    if err:
        return err

    update_draft_status(draft_id, 'REJECTED')
    return _html(200, "Rejected.")


def get_queue_json(event, jinja_env):
    """GET /api/admin/queue — JSON draft review queue."""
    claims, err = _admin_check(event)
    if err:
        return err

    drafts = get_drafts_by_status('pending')
    return _json(200, {'drafts': drafts})


def get_draft_json(event, jinja_env, draft_id):
    """GET /api/admin/drafts/{id} — JSON draft detail."""
    claims, err = _admin_check(event)
    if err:
        return err

    draft = db_get_draft(draft_id)
    if not draft:
        return _json(404, {'error': 'Draft not found'})

    return _json(200, {'draft': draft})


def approve_draft_json(event, jinja_env, draft_id):
    """POST /api/admin/drafts/{id}/approve — approve a draft and return JSON."""
    claims, err = _admin_check(event)
    if err:
        return err

    data = _parse_body(event)
    cats = data.get('categories', [])
    if isinstance(cats, str):
        cats = [cats] if cats else []
    data['categories'] = cats

    draft = db_get_draft(draft_id)
    if not draft:
        return _json(404, {'error': 'Draft not found'})

    draft_type = draft.get('draft_type', 'event')
    merged = {k: v for k, v in draft.items() if v is not None}
    merged.update({k: v for k, v in data.items() if v is not None})

    commit_url = None
    try:
        if draft_type == 'group':
            from github_commit import commit_group_to_repo
            commit_url = commit_group_to_repo(merged)
        else:
            from github_commit import commit_event_to_repo
            commit_url = commit_event_to_repo(merged)
    except Exception as e:
        print(f"WARNING: GitHub commit failed (non-blocking): {e}")

    update_draft_status(draft_id, 'APPROVED', claims.get('email', ''), commit_url=commit_url)
    label = 'group' if draft_type == 'group' else 'event'
    return _json(200, {'message': f'Approved and committed {label} to repo.', 'commit_url': commit_url})


def reject_draft_json(event, jinja_env, draft_id):
    """POST /api/admin/drafts/{id}/reject — reject a draft and return JSON."""
    claims, err = _admin_check(event)
    if err:
        return err

    draft = db_get_draft(draft_id)
    if not draft:
        return _json(404, {'error': 'Draft not found'})

    update_draft_status(draft_id, 'REJECTED')
    return _json(200, {'message': 'Rejected.'})


# ─── Newsletter Subscribers ──────────────────────────────────────────

def get_subscribers(event, jinja_env):
    """GET /admin/subscribers — Newsletter subscribers page."""
    claims, err = _admin_check(event)
    if err:
        return err

    template = jinja_env.get_template('admin/subscribers.html')
    html = template.render(claims=claims)
    return _html(200, html, event)


def get_subscribers_json(event, jinja_env):
    """GET /api/admin/subscribers — Return subscribers as JSON."""
    claims, err = _admin_check(event)
    if err:
        # Ensure error response has proper headers
        if 'headers' not in err:
            err['headers'] = {'Content-Type': 'application/json'}
        return err

    try:
        sesv2 = boto3.client('sesv2', region_name='us-east-1')
        response = sesv2.list_contacts(ContactListName='newsletters')
        
        contacts = response.get('Contacts', [])
        # Sort by CreatedTimestamp (newest first)
        contacts.sort(key=lambda x: x.get('CreatedTimestamp', ''), reverse=True)
        
        subscribers = [{
            'email': c['EmailAddress'],
            'subscribed_at': c.get('CreatedTimestamp', ''),
            'unsubscribe_all': c.get('UnsubscribeAll', False),
        } for c in contacts]
        
        return _json(200, {
            'subscribers': subscribers,
            'count': len(subscribers)
        })
    except Exception as e:
        print(f"Error fetching subscribers: {e}")
        return _json(500, {'error': str(e)})
