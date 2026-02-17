"""
Admin routes (requires authentication + admins group).

All routes return HTML fragments for HTMX swap.
"""

import json

from auth import get_user_from_event, require_admin
from db import (
    get_drafts_by_status, get_draft as db_get_draft, update_draft_status,
    get_all_groups, get_group, put_group,
    get_all_overrides as db_get_all_overrides, get_override,
    put_override as db_put_override, delete_override as db_delete_override,
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


def _html(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'text/html; charset=utf-8',
            'Access-Control-Allow-Origin': '*',
        },
        'body': body,
    }


def _parse_body(event):
    body = event.get('body', '')
    if not body:
        return {}
    content_type = (event.get('headers', {}).get('Content-Type', '') or
                    event.get('headers', {}).get('content-type', ''))
    if 'application/json' in content_type:
        return json.loads(body)
    from urllib.parse import parse_qs
    parsed = parse_qs(body)
    return {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}


# ─── Dashboard ────────────────────────────────────────────────────

def dashboard(event, jinja_env):
    """GET /admin — admin dashboard summary."""
    claims, err = _admin_check(event)
    if err:
        return err

    pending = get_drafts_by_status('pending')
    groups = get_all_groups()

    template = jinja_env.get_template('partials/admin_dashboard.html')
    html = template.render(
        pending_count=len(pending),
        groups_count=len(groups),
        user_email=claims.get('email', ''),
    )
    return _html(200, html)


# ─── Queue (drafts) ──────────────────────────────────────────────

def get_queue(event, jinja_env):
    """GET /admin/queue — HTML table of pending drafts."""
    claims, err = _admin_check(event)
    if err:
        return err

    drafts = get_drafts_by_status('pending')
    template = jinja_env.get_template('partials/draft_queue.html')
    html = template.render(drafts=drafts)
    return _html(200, html)


def get_draft(event, jinja_env, draft_id):
    """GET /admin/draft/{id} — single draft detail."""
    claims, err = _admin_check(event)
    if err:
        return err

    draft = db_get_draft(draft_id)
    if not draft:
        return _html(404, '<p>Draft not found</p>')

    template = jinja_env.get_template('partials/draft_detail.html')
    html = template.render(draft=draft)
    return _html(200, html)


def approve_draft(event, jinja_env, draft_id):
    """POST /admin/draft/{id}/approve — approve and return updated row."""
    claims, err = _admin_check(event)
    if err:
        return err

    draft = db_get_draft(draft_id)
    if not draft:
        return _html(404, '<p>Draft not found</p>')

    reviewer = claims.get('email', '')
    update_draft_status(draft_id, 'approved', reviewer)

    # Return empty string to remove the row via hx-swap="outerHTML"
    return _html(200, '')


def reject_draft(event, jinja_env, draft_id):
    """POST /admin/draft/{id}/reject — reject and return updated row."""
    claims, err = _admin_check(event)
    if err:
        return err

    draft = db_get_draft(draft_id)
    if not draft:
        return _html(404, '<p>Draft not found</p>')

    reviewer = claims.get('email', '')
    update_draft_status(draft_id, 'rejected', reviewer)

    return _html(200, '')


# ─── Groups ──────────────────────────────────────────────────────

def get_groups(event, jinja_env):
    """GET /admin/groups — HTML table of groups."""
    claims, err = _admin_check(event)
    if err:
        return err

    groups = get_all_groups()
    groups.sort(key=lambda x: x.get('name', '').lower())
    categories = get_all_categories()

    template = jinja_env.get_template('partials/group_list.html')
    html = template.render(groups=groups, categories=categories)
    return _html(200, html)


def edit_group_form(event, jinja_env, slug):
    """GET /admin/groups/{slug}/edit — HTML form fragment."""
    claims, err = _admin_check(event)
    if err:
        return err

    group = get_group(slug)
    if not group:
        return _html(404, '<p>Group not found</p>')

    categories = get_all_categories()
    template = jinja_env.get_template('partials/group_form.html')
    html = template.render(group=group, categories=categories)
    return _html(200, html)


def update_group(event, jinja_env, slug):
    """PUT /admin/groups/{slug} — save group, return updated row."""
    claims, err = _admin_check(event)
    if err:
        return err

    data = _parse_body(event)

    group = get_group(slug)
    if not group:
        return _html(404, '<p>Group not found</p>')

    # Update fields
    group['name'] = data.get('name', group.get('name', ''))
    group['website'] = data.get('website', group.get('website', ''))
    group['ical'] = data.get('ical', group.get('ical', ''))
    group['active'] = data.get('active', 'true') in ('true', True, '1', 1)

    categories_val = data.get('categories', [])
    if isinstance(categories_val, str):
        categories_val = [c.strip() for c in categories_val.split(',') if c.strip()]
    group['categories'] = categories_val

    put_group(slug, group)

    template = jinja_env.get_template('partials/group_row.html')
    html = template.render(group=group)
    return _html(200, html)


# ─── Overrides ───────────────────────────────────────────────────

def get_overrides(event, jinja_env):
    """GET /admin/overrides — HTML table of overrides."""
    claims, err = _admin_check(event)
    if err:
        return err

    overrides = db_get_all_overrides()
    template = jinja_env.get_template('partials/override_list.html')
    html = template.render(overrides=overrides)
    return _html(200, html)


def create_override(event, jinja_env):
    """POST /admin/overrides — create a new override."""
    claims, err = _admin_check(event)
    if err:
        return err

    data = _parse_body(event)
    guid = data.get('guid', '').strip()
    if not guid:
        return _html(400, '<p>GUID is required</p>')

    override_data = {}
    for field in ['categories', 'title', 'url', 'location', 'time', 'hidden', 'duplicate_of']:
        if field in data:
            override_data[field] = data[field]

    override_data['edited_by'] = claims.get('email', '')

    db_put_override(guid, override_data)

    override = {'guid': guid, **override_data}
    template = jinja_env.get_template('partials/override_row.html')
    html = template.render(override=override)
    return _html(201, html)


def delete_override(event, jinja_env, guid):
    """DELETE /admin/overrides/{guid} — delete override, return empty."""
    claims, err = _admin_check(event)
    if err:
        return err

    db_delete_override(guid)
    return _html(200, '')
