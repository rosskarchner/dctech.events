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
    get_all_overrides as db_get_all_overrides, get_override,
    put_override as db_put_override, delete_override as db_delete_override,
    get_all_categories, get_events_by_date,
    get_all_events, get_event_from_config, update_event as db_update_event,
    get_materialized_event,
    bulk_delete_events, bulk_set_category, bulk_combine_events,
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

    # Promote event drafts to EVENT# entities so they appear in the API
    if draft.get('draft_type') == 'event':
        promote_draft_to_event(draft)

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


# ─── Events ──────────────────────────────────────────────────────

def get_events(event, jinja_env):
    """GET /admin/events — HTML table from DcTechEvents materialized view."""
    claims, err = _admin_check(event)
    if err:
        return err

    params = event.get('queryStringParameters') or {}
    date_prefix = params.get('date', '').strip() or None

    events = get_all_events(date_prefix)
    all_categories = get_all_categories()

    template = jinja_env.get_template('partials/admin_events.html')
    html = template.render(events=events, date_filter=date_prefix or '',
                           all_categories=all_categories)
    return _html(200, html)


def get_event_edit_form(event, jinja_env, guid):
    """GET /admin/events/{guid}/edit — inline edit form row."""
    claims, err = _admin_check(event)
    if err:
        return err

    all_categories = get_all_categories()
    manual = get_event_from_config(guid)
    if manual:
        template = jinja_env.get_template('partials/admin_event_edit_form.html')
        html = template.render(event=manual, all_categories=all_categories)
    else:
        mat_event = get_materialized_event(guid) or {}
        override = get_override(guid) or {}
        template = jinja_env.get_template('partials/admin_event_override_form.html')
        html = template.render(guid=guid, event=mat_event, override=override,
                               all_categories=all_categories)
    return _html(200, html)


def save_event_edit(event, jinja_env, guid):
    """PUT /admin/events/{guid} — save edit and return updated row."""
    claims, err = _admin_check(event)
    if err:
        return err

    data = _parse_body(event)

    # Normalize categories: checkboxes send repeated values or nothing
    cats = data.get('categories', [])
    if isinstance(cats, str):
        cats = [cats] if cats else []
    data['categories'] = cats

    # Normalize checkbox and text fields
    data['hidden'] = data.get('hidden') == 'true'
    data['duplicate_of'] = data.get('duplicate_of', '').strip() or None

    manual = get_event_from_config(guid)

    if manual:
        db_update_event(guid, data)
        updated = get_event_from_config(guid) or {}
        updated['guid'] = guid
    else:
        # For iCal events, create or update an override
        override_data = {'edited_by': claims.get('email', '')}
        # Fields we allow overriding for iCal events
        for field in ['title', 'location', 'categories', 'url', 'time', 'hidden', 'duplicate_of']:
            if field in data:
                override_data[field] = data[field]
        
        db_put_override(guid, override_data)
        
        # Merge materialized event with override for display in the updated row
        base_event = get_materialized_event(guid) or {}
        updated = dict(base_event)
        for field, val in override_data.items():
            if val is not None:
                updated[field] = val
        updated['guid'] = guid

    template = jinja_env.get_template('partials/admin_event_row.html')
    html = template.render(event=updated)
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


def handle_bulk_action(event, jinja_env):
    """POST /admin/events/bulk — handle bulk actions on events."""
    claims, err = _admin_check(event)
    if err:
        return err

    data = _parse_body(event)
    action = data.get('action')
    guids = data.get('guids', [])
    if isinstance(guids, str):
        guids = [guids]
    
    if not guids:
        return _html(400, '<p>No events selected</p>')

    actor = claims.get('email', 'unknown')

    if action == 'delete':
        bulk_delete_events(guids, actor)
    elif action == 'category':
        cat_slug = data.get('category_slug')
        if not cat_slug:
            return _html(400, '<p>No category selected</p>')
        bulk_set_category(guids, cat_slug, actor)
    elif action == 'combine':
        target_guid = data.get('target_guid')
        if not target_guid:
            # Default to the first one in the list? Or require one?
            # Better to require one or pick the most "materialized" one.
            target_guid = guids[0]
        bulk_combine_events(guids, target_guid, actor)
    else:
        return _html(400, f'<p>Unknown action: {action}</p>')

    # After bulk action, reload the event list
    # The date filter might be in query params (GET) or body (POST from bulk include)
    date_prefix = data.get('date', '').strip()
    if not date_prefix:
        params = event.get('queryStringParameters') or {}
        date_prefix = params.get('date', '').strip()
    
    if not date_prefix:
        date_prefix = None
        
    events = get_all_events(date_prefix)
    all_categories = get_all_categories()
    
    template = jinja_env.get_template('partials/admin_events.html')
    html = template.render(events=events, date_filter=date_prefix or '',
                           all_categories=all_categories)
    
    # We add a success message header
    return _html(200, html)
