"""
Tool implementations for the DC Tech Events MCP server.

Reuses dynamo_data.py and versioned_db.py directly.
"""

import json
import os
import sys
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dynamo_data
import versioned_db


def _json(obj):
    """Serialize to JSON, handling Decimal and other types."""
    from decimal import Decimal
    def default(o):
        if isinstance(o, Decimal):
            return float(o) if o % 1 else int(o)
        if isinstance(o, set):
            return list(o)
        return str(o)
    return json.dumps(obj, indent=2, default=default)


def _pk_for(entity_type, entity_id):
    """Build PK from entity type and ID."""
    if entity_type == 'event':
        return f'EVENT#{entity_id}'
    elif entity_type == 'group':
        return f'GROUP#{entity_id}'
    raise ValueError(f"Unknown entity_type: {entity_type}")


# ─── Read tools ───────────────────────────────────────────────────

def query_events(date_from="", date_to="", category="", group="",
                 search_text="", limit=50):
    """Query upcoming events with filters."""
    events = dynamo_data.get_future_events()

    # Date filtering
    if date_from:
        events = [e for e in events if str(e.get('date', '')) >= date_from]
    if date_to:
        events = [e for e in events if str(e.get('date', '')) <= date_to]

    # Category filter
    if category:
        events = [e for e in events if category in (e.get('categories') or [])]

    # Group filter
    if group:
        group_lower = group.lower()
        events = [e for e in events if group_lower in str(e.get('group', '')).lower()]

    # Text search
    if search_text:
        q = search_text.lower()
        events = [e for e in events if (
            q in str(e.get('title', '')).lower() or
            q in str(e.get('description', '')).lower() or
            q in str(e.get('group', '')).lower() or
            q in str(e.get('location', '')).lower()
        )]

    # Filter out hidden/duplicates
    events = [e for e in events if not e.get('hidden') and not e.get('duplicate_of')]

    events = events[:limit]

    if not events:
        return "No events found matching the criteria."

    lines = [f"Found {len(events)} events:\n"]
    for e in events:
        cats = ', '.join(e.get('categories', []))
        lines.append(
            f"- [{e.get('date', '?')} {e.get('time', '')}] "
            f"{e.get('title', '?')} | {e.get('group', '?')} | "
            f"{e.get('location', '?')} | guid={e.get('guid', '?')}"
            f"{f' [{cats}]' if cats else ''}"
        )
    return '\n'.join(lines)


def get_event(guid):
    """Get a single event with full detail."""
    table = dynamo_data._get_table()
    response = table.get_item(Key={'PK': f'EVENT#{guid}', 'SK': 'META'})
    item = response.get('Item')

    if not item:
        return f"Event {guid} not found."

    event = dynamo_data._dynamo_item_to_event_full(item)

    # Include recent history
    history = versioned_db.get_history(f'EVENT#{guid}', limit=5)
    event['recent_history'] = [
        {'timestamp': h['timestamp'], 'editor': h['editor'], 'reason': h['reason']}
        for h in history
    ]

    return _json(event)


def list_groups(active_only=True):
    """List groups."""
    if active_only:
        groups = dynamo_data.get_active_groups()
    else:
        groups = dynamo_data.get_all_groups()

    if not groups:
        return "No groups found."

    lines = [f"Found {len(groups)} groups:\n"]
    for g in groups:
        status = "active" if g.get('active', True) else "inactive"
        cats = ', '.join(g.get('categories', []))
        lines.append(
            f"- {g.get('name', '?')} (slug={g.get('id', '?')}) [{status}]"
            f"{f' categories=[{cats}]' if cats else ''}"
            + (f" ical={g['ical']}" if g.get('ical') else "")
        )
    return '\n'.join(lines)


def get_group(slug):
    """Get a single group."""
    table = dynamo_data._get_table()
    response = table.get_item(Key={'PK': f'GROUP#{slug}', 'SK': 'META'})
    item = response.get('Item')
    if not item:
        return f"Group '{slug}' not found."
    group = dynamo_data._dynamo_item_to_group(item)
    return _json(group)


def list_categories():
    """List all categories."""
    cats = dynamo_data.get_all_categories()
    if not cats:
        return "No categories found."
    lines = [f"Found {len(cats)} categories:\n"]
    for slug, cat in sorted(cats.items()):
        lines.append(f"- {cat['name']} (slug={slug}): {cat.get('description', '')}")
    return '\n'.join(lines)


def get_recently_added(limit=20):
    """Get recently added events."""
    events = dynamo_data.get_recently_added(limit=limit)
    events = [e for e in events if not e.get('hidden') and not e.get('duplicate_of')]

    if not events:
        return "No recently added events found."

    lines = [f"Recently added events ({len(events)}):\n"]
    for e in events:
        lines.append(
            f"- [{e.get('createdAt', '?')}] {e.get('title', '?')} "
            f"({e.get('date', '?')}) | {e.get('group', '?')} | guid={e.get('guid', '?')}"
        )
    return '\n'.join(lines)


def search(query, limit=20):
    """Full-text search across events."""
    return query_events(search_text=query, limit=limit)


# ─── Write tools ──────────────────────────────────────────────────

def edit_event(guid, changes, reason):
    """Edit event fields with versioning."""
    table = dynamo_data._get_table()
    pk = f'EVENT#{guid}'

    existing = table.get_item(Key={'PK': pk, 'SK': 'META'}).get('Item')
    if not existing:
        return f"Event {guid} not found."

    # Build updated item
    updated = dict(existing)
    overrides_map = updated.get('overrides', {})

    for field, value in changes.items():
        if field in ('PK', 'SK', 'source'):
            continue
        updated[field] = value
        # Track that this field was manually edited
        if existing.get('source') == 'ical':
            overrides_map[field] = True

    if overrides_map:
        updated['overrides'] = overrides_map

    # Remove PK/SK for versioned_put (it sets them)
    item = {k: v for k, v in updated.items() if k not in ('PK', 'SK')}

    versioned_db.versioned_put(
        pk=pk,
        item=item,
        editor='mcp-server',
        reason=reason,
    )
    return f"Event {guid} updated. Changed: {', '.join(changes.keys())}"


def edit_group(slug, changes, reason):
    """Edit group fields with versioning."""
    table = dynamo_data._get_table()
    pk = f'GROUP#{slug}'

    existing = table.get_item(Key={'PK': pk, 'SK': 'META'}).get('Item')
    if not existing:
        return f"Group '{slug}' not found."

    updated = dict(existing)
    for field, value in changes.items():
        if field in ('PK', 'SK'):
            continue
        updated[field] = value

    item = {k: v for k, v in updated.items() if k not in ('PK', 'SK')}

    versioned_db.versioned_put(
        pk=pk,
        item=item,
        editor='mcp-server',
        reason=reason,
    )
    return f"Group '{slug}' updated. Changed: {', '.join(changes.keys())}"


def hide_event(guid, reason):
    """Hide an event."""
    return edit_event(guid, {'hidden': True}, reason)


def unhide_event(guid, reason):
    """Unhide an event."""
    return edit_event(guid, {'hidden': False}, reason)


def mark_duplicate(guid, duplicate_of, reason):
    """Mark an event as duplicate of another."""
    return edit_event(guid, {'duplicate_of': duplicate_of}, reason)


def set_event_categories(guid, categories, reason):
    """Set categories for an event."""
    return edit_event(guid, {'categories': categories}, reason)


# ─── History tools ────────────────────────────────────────────────

def get_history(entity_type, entity_id, limit=10):
    """View change history."""
    pk = _pk_for(entity_type, entity_id)
    entries = versioned_db.get_history(pk, limit=limit)

    if not entries:
        return f"No history found for {entity_type} '{entity_id}'."

    lines = [f"History for {entity_type} '{entity_id}' ({len(entries)} entries):\n"]
    for entry in entries:
        lines.append(
            f"- [{entry.get('timestamp', '?')}] by {entry.get('editor', '?')}: "
            f"{entry.get('reason', '(no reason)')}"
        )
    return '\n'.join(lines)


def rollback(entity_type, entity_id, version_timestamp, reason):
    """Rollback to a previous version."""
    pk = _pk_for(entity_type, entity_id)

    try:
        versioned_db.rollback(
            pk=pk,
            version_ts=version_timestamp,
            editor='mcp-server',
        )
        return f"Rolled back {entity_type} '{entity_id}' to version {version_timestamp}."
    except ValueError as e:
        return str(e)
