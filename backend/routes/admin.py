"""
Admin routes (requires authentication + admins group).

All routes return HTML fragments for HTMX swap.
"""

import json

from auth import get_user_from_event, require_admin
from db import (
    get_drafts_by_status, get_draft as db_get_draft, update_draft_status,
    promote_draft_to_event,
    get_all_groups, get_group, put_group,
    get_all_categories, get_events_by_date,
    get_all_events, get_event_from_config, update_event as db_update_event,
    bulk_delete_events, bulk_set_category, bulk_combine_events,
    put_category as db_put_category, delete_category as db_delete_category,
)


def _admin_check(event):
    """Validate auth + admin group. Returns (claims, error_response)."""
    claims, err = get_user_from_event(event)
    if err:
        return None, err
    if not require_admin(claims):
        return None, {'statusCode': 403, 'body': 'Forbidden'}
    return claims, None


def _html(status_code, body, event=None):
    """Return HTML response."""
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'text/html'},
        'body': body,
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

    drafts = get_drafts_by_status('PENDING')
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
    """POST /admin/draft/{id}/approve."""
    claims, err = _admin_check(event)
    if err:
        return err

    data = _parse_body(event)
    
    # Normalize categories
    cats = data.get('categories', [])
    if isinstance(cats, str):
        cats = [cats] if cats else []
    data['categories'] = cats

    promote_draft_to_event(draft_id, data, claims.get('email', ''))
    
    return _html(200, "Approved and promoted to event.")


def reject_draft(event, jinja_env, draft_id):
    """POST /admin/draft/{id}/reject."""
    claims, err = _admin_check(event)
    if err:
        return err

    update_draft_status(draft_id, 'REJECTED')
    return _html(200, "Rejected.")


# ─── Groups ───────────────────────────────────────────────────────

def get_groups(event, jinja_env):
    """GET /admin/groups — HTML table of groups."""
    claims, err = _admin_check(event)
    if err:
        return err

    groups = get_all_groups()
    template = jinja_env.get_template('partials/admin_group_list.html')
    html = template.render(groups=groups)
    return _html(200, html, event)


def edit_group_form(event, jinja_env, slug):
    """GET /admin/group/{slug}/edit — HTML form."""
    claims, err = _admin_check(event)
    if err:
        return err

    group = get_group(slug)
    template = jinja_env.get_template('partials/admin_group_edit_form.html')
    html = template.render(group=group)
    return _html(200, html, event)


def update_group(event, jinja_env, slug):
    """POST /admin/group/{slug}."""
    claims, err = _admin_check(event)
    if err:
        return err

    data = _parse_body(event)
    data['active'] = data.get('active') == 'true'
    
    put_group(slug, data)
    
    # Return updated row
    group = get_group(slug)
    template = jinja_env.get_template('partials/admin_group_row.html')
    html = template.render(group=group)
    return _html(200, html, event)


# ─── Events ───────────────────────────────────────────────────────

def get_events(event, jinja_env):
    """GET /admin/events — List manual events."""
    claims, err = _admin_check(event)
    if err:
        return err

    params = event.get('queryStringParameters') or {}
    date_prefix = params.get('date')
    
    events = get_all_events(date_prefix)
    # Only show non-ical events in the manual event list
    events = [e for e in events if e.get('source') != 'ical']
    
    template = jinja_env.get_template('partials/admin_event_list.html')
    html = template.render(events=events)
    return _html(200, html, event)


def get_event_edit_form(event, jinja_env, guid):
    """GET /admin/events/{guid}/edit — HTML form."""
    claims, err = _admin_check(event)
    if err:
        return err

    all_categories = get_all_categories()
    mat_event = get_event_from_config(guid) or {}
    if not mat_event:
        return {'statusCode': 404, 'body': 'Event not found'}

    template = jinja_env.get_template('partials/admin_event_edit_form.html')
    html = template.render(event=mat_event, all_categories=all_categories)
    return _html(200, html, event)


def save_event_edit(event, jinja_env, guid):
    """PUT /admin/events/{guid} — save edit and return updated row."""
    claims, err = _admin_check(event)
    if err:
        return err

    data = _parse_body(event)

    # Normalize categories
    cats = data.get('categories', [])
    if isinstance(cats, str):
        cats = [cats] if cats else []
    data['categories'] = cats

    # Normalize checkbox and text fields
    data['hidden'] = data.get('hidden') == 'true'
    data['duplicate_of'] = data.get('duplicate_of', '').strip() or None

    db_update_event(guid, data)
    updated = get_event_from_config(guid) or {}
    updated['guid'] = guid

    template = jinja_env.get_template('partials/admin_event_row.html')
    html = template.render(event=updated)
    return _html(200, html, event)


# ─── Bulk Actions ────────────────────────────────────────────────

def handle_bulk_action(event, jinja_env):
    """POST /admin/events/bulk — Handle hide/categorize/combine."""
    claims, err = _admin_check(event)
    if err:
        return err

    data = _parse_body(event)
    action = data.get('action')
    guids = data.get('guids', [])
    if isinstance(guids, str):
        guids = [guids]

    if not guids:
        return {'statusCode': 400, 'body': 'No events selected'}

    actor = claims.get('email', '')

    if action == 'hide':
        bulk_delete_events(guids, actor)
    elif action == 'categorize':
        cat = data.get('category')
        if cat:
            bulk_set_category(guids, cat, actor)
    elif action == 'combine':
        target = data.get('target_guid')
        if target:
            bulk_combine_events(guids, target, actor)

    return _html(200, f"Bulk action '{action}' completed for {len(guids)} events.")


# ─── Categories ──────────────────────────────────────────────────

def get_categories(event, jinja_env):
    """GET /admin/categories — HTML list."""
    claims, err = _admin_check(event)
    if err:
        return err

    categories = get_all_categories()
    template = jinja_env.get_template('partials/admin_category_list.html')
    html = template.render(categories=categories)
    return _html(200, html, event)


def create_category(event, jinja_env):
    """POST /admin/categories — create new."""
    claims, err = _admin_check(event)
    if err:
        return err

    data = _parse_body(event)
    slug = data.get('slug', '').strip().lower()
    if not slug:
        return {'statusCode': 400, 'body': 'Missing slug'}

    db_put_category(slug, data)
    
    # Return updated list
    return get_categories(event, jinja_env)


def get_category_edit_form(event, jinja_env, slug):
    """GET /admin/category/{slug}/edit."""
    # Similar to others...
    return _html(200, "Not implemented yet")


def update_category(event, jinja_env, slug):
    """POST /admin/category/{slug}."""
    return create_category(event, jinja_env)


def delete_category_route(event, jinja_env, slug):
    """DELETE /admin/category/{slug}."""
    claims, err = _admin_check(event)
    if err:
        return err

    db_delete_category(slug)
    return _html(200, "")
