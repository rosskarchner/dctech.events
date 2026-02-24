"""
DC Tech Events MCP Server.

Provides tools for agent-based event database manipulation via the
Model Context Protocol (MCP). Uses stdio transport.

Usage:
    python -m mcp_server.server
"""

import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP

from mcp_server.tools import (
    query_events,
    get_event,
    list_groups,
    get_group,
    list_categories,
    get_recently_added,
    search,
    edit_event,
    edit_group,
    hide_event,
    unhide_event,
    mark_duplicate,
    set_event_categories,
    get_history,
    rollback,
)

mcp = FastMCP("dctech-events")

# ─── Read tools ───────────────────────────────────────────────────

@mcp.tool()
def tool_query_events(
    date_from: str = "",
    date_to: str = "",
    category: str = "",
    group: str = "",
    search_text: str = "",
    limit: int = 50,
) -> str:
    """Query upcoming events with optional filters.

    Args:
        date_from: Start date (YYYY-MM-DD). Defaults to today.
        date_to: End date (YYYY-MM-DD). Defaults to 90 days out.
        category: Filter by category slug (e.g. 'ai', 'cybersecurity').
        group: Filter by group name.
        search_text: Search across title, description, group, location.
        limit: Max results (default 50).
    """
    return query_events(date_from, date_to, category, group, search_text, limit)


@mcp.tool()
def tool_get_event(guid: str) -> str:
    """Get a single event with full detail including history.

    Args:
        guid: Event GUID (MD5 hash).
    """
    return get_event(guid)


@mcp.tool()
def tool_list_groups(active_only: bool = True) -> str:
    """List tech meetup groups.

    Args:
        active_only: If true, only return active groups.
    """
    return list_groups(active_only)


@mcp.tool()
def tool_get_group(slug: str) -> str:
    """Get a single group by slug with full detail.

    Args:
        slug: Group slug identifier.
    """
    return get_group(slug)


@mcp.tool()
def tool_list_categories() -> str:
    """List all event categories."""
    return list_categories()


@mcp.tool()
def tool_get_recently_added(limit: int = 20) -> str:
    """Get most recently added events.

    Args:
        limit: Max results (default 20).
    """
    return get_recently_added(limit)


@mcp.tool()
def tool_search(query: str, limit: int = 20) -> str:
    """Full-text search across events (title, description, group, location).

    Args:
        query: Search query string.
        limit: Max results (default 20).
    """
    return search(query, limit)


# ─── Write tools ──────────────────────────────────────────────────

@mcp.tool()
def tool_edit_event(guid: str, changes: dict, reason: str) -> str:
    """Edit event fields. Creates a versioned history entry.

    Args:
        guid: Event GUID.
        changes: Dict of fields to update (e.g. {"title": "New Title", "categories": ["ai"]}).
        reason: Why this change is being made.
    """
    return edit_event(guid, changes, reason)


@mcp.tool()
def tool_edit_group(slug: str, changes: dict, reason: str) -> str:
    """Edit group fields. Creates a versioned history entry.

    Args:
        slug: Group slug.
        changes: Dict of fields to update.
        reason: Why this change is being made.
    """
    return edit_group(slug, changes, reason)


@mcp.tool()
def tool_hide_event(guid: str, reason: str) -> str:
    """Hide an event (sets hidden=true). Creates a versioned history entry.

    Args:
        guid: Event GUID.
        reason: Why this event is being hidden.
    """
    return hide_event(guid, reason)


@mcp.tool()
def tool_unhide_event(guid: str, reason: str) -> str:
    """Unhide a previously hidden event. Creates a versioned history entry.

    Args:
        guid: Event GUID.
        reason: Why this event is being unhidden.
    """
    return unhide_event(guid, reason)


@mcp.tool()
def tool_mark_duplicate(guid: str, duplicate_of: str, reason: str) -> str:
    """Mark an event as a duplicate of another event.

    Args:
        guid: GUID of the duplicate event.
        duplicate_of: GUID of the original/canonical event.
        reason: Why these are considered duplicates.
    """
    return mark_duplicate(guid, duplicate_of, reason)


@mcp.tool()
def tool_set_event_categories(guid: str, categories: list, reason: str) -> str:
    """Set categories for an event (replaces existing categories).

    Args:
        guid: Event GUID.
        categories: List of category slugs.
        reason: Why categories are being changed.
    """
    return set_event_categories(guid, categories, reason)


# ─── History tools ────────────────────────────────────────────────

@mcp.tool()
def tool_get_history(entity_type: str, entity_id: str, limit: int = 10) -> str:
    """View change history for an entity.

    Args:
        entity_type: 'event' or 'group'.
        entity_id: GUID (for events) or slug (for groups).
        limit: Max history entries (default 10).
    """
    return get_history(entity_type, entity_id, limit)


@mcp.tool()
def tool_rollback(entity_type: str, entity_id: str, version_timestamp: str, reason: str) -> str:
    """Rollback an entity to a previous version.

    Args:
        entity_type: 'event' or 'group'.
        entity_id: GUID (for events) or slug (for groups).
        version_timestamp: ISO timestamp of the version to restore.
        reason: Why rolling back.
    """
    return rollback(entity_type, entity_id, version_timestamp, reason)


if __name__ == "__main__":
    mcp.run(transport="stdio")
