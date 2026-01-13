# Event Edit Functionality

## Overview

Users who are logged in via GitHub OAuth can edit events. Edits flow through the standard GitHub pull request workflow, maintaining consistency with existing event submission and group submission pages.

**Scope:**
- Edit button appears only for authenticated GitHub users
- Both manually-submitted events (from `_single_events/`) and iCal feed events can be edited
- Manual events: existing `_single_events/` file is updated directly
- iCal feed events: override files are created in `_event_overrides/` directory

## User Experience

### Edit Button Visibility
- An "Edit" button appears on event detail pages only when a user is logged in to GitHub
- The button links to the edit form for that specific event
- Button placement: [TBD - decide placement on event detail page]

### Edit Form
- Pre-populated with current event data
- **Locked field**: Event source (indicates whether from iCal feed or manually submitted)
- **Editable fields**: title, date, time, location, url, cost, group, description, and any other event fields
- **Validation**: Location must be in "City, State" format (e.g., "Washington, DC" or "Arlington, VA")
- Follows same design/UX as existing `/submit/` and `/submit-group/` pages

## Data Storage

### Manual Events (from `_single_events/`)
- Edit updates the existing YAML file in `_single_events/`
- File path: `_single_events/{slug}.yaml`

### iCal Feed Events (Override Mechanism)
- Edits create override files in `_event_overrides/` directory
- Override files are YAML format, same structure as `_single_events/` files
- Override takes precedence when `refresh_calendars.py` processes iCal feeds

#### Override File Naming
- Filename: `{event_hash}.yaml`
- Hash calculation uses same algorithm as iCal GUID generation:
  1. Combine: `date + time + title + (optional) url`
  2. Convert to MD5 hash
  3. Filename: `{md5_hash}.yaml`
  
Example:
```
_event_overrides/a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6.yaml
```

#### Override File Content
- Contains only the fields being overridden
- Must preserve enough information to link back to the original iCal event
- Structure:
```yaml
# Fields being overridden
title: "Modified Event Title"
location: "New City, DC"
url: "https://new-url.example.com"
# ... other edited fields

# Metadata for tracking (optional but recommended)
source_ical_url: "https://original-ical-feed-url"  # For reference
original_title: "Original Title"  # Helpful for debugging
original_event_hash: "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
```

### Soft Delete via Group YAML
- To delete an iCal event, use existing soft-delete mechanism in `_groups/{group_id}.yaml`
- Add event to the group's `disabled_events` list
- This approach prevents reappearance if iCal feed is refreshed

## GitHub PR Workflow

### PR Creation
1. User submits edit form with modified event data
2. System generates:
   - For manual events: modified `_single_events/{slug}.yaml` file
   - For iCal events: new `_event_overrides/{hash}.yaml` file
3. PR is created with modified/new file

### PR Description
- Title: `Edit event: {event_title}`
- Description includes:
  - **Diff showing changes**: Side-by-side or unified diff of old values → new values
  - Fields changed with original and new values clearly visible
  - For iCal overrides: note which iCal feed the event originates from
  - Example format:
    ```
    **Event:** My Tech Talk
    **Changed fields:**
    - location: "Washington, DC" → "Arlington, VA"
    - time: "18:00" → "19:00"
    - url: "https://old-url.com" → "https://new-url.com"
    ```

### PR Merge
- Standard review and merge process (no auto-merge for now)
- PR merges to `main` branch
- Changes appear on site after static site regeneration

## Technical Implementation

### Backend Changes (app.py)
1. Add `/edit/<event_id>/` route to display edit form
2. Add `/edit-submit/` POST endpoint to handle form submission
3. Event ID format:
   - Manual events: slug from filename
   - iCal events: the MD5 hash used for override naming
4. Endpoint authenticates user is logged in to GitHub
5. Loads current event data to pre-populate form
6. Generates GitHub PR with appropriate file changes

### Override File Generation
- Hash calculation function matching iCal GUID generation logic (from app.py lines 1110-1123)
- Idempotent: same input always generates same hash
- Used for both initial override file creation and subsequent edits

### Integration with refresh_calendars.py
- When processing iCal feeds, check `_event_overrides/` for matching hash
- If override file exists: merge override data with iCal event data (overrides take precedence)
- Existing events with overrides should be updated with override fields on each refresh

### Integration with generate_month_data.py
- Ensure both manual events and iCal events with overrides are included in `upcoming.yaml`
- Override data takes precedence in merged output

## Validation Rules

### Location Validation
- Must be in "City, State" format
- Examples (valid): "Washington, DC", "Arlington, VA", "Baltimore, MD", "New York, NY"
- Invalid patterns: just city, just state, no comma, etc.
- Validation happens client-side and server-side

### Other Fields
- title: required, non-empty
- date: required, valid YYYY-MM-DD format, future date
- time: optional, valid HH:MM format if provided
- url: optional, valid URL format if provided
- cost: optional, string
- group: optional, string

## Event Categorization

### Overview
Events can be tagged with one or more categories to help users filter and discover events by topic. Categories are managed as YAML files in a new `_categories/` directory.

### Category Structure

#### Category File Format
Location: `_categories/{slug}.yaml`

```yaml
name: "AI and Machine Learning"
description: "Events focused on artificial intelligence, machine learning, and related technologies"
```

- **slug** (filename): Unique identifier for the category (e.g., `ai`, `python`, `gaming`)
- **name** (required): Human-readable category name
- **description** (required): Text description of what events belong in this category

### Initial Categories

The following categories will be created in `_categories/`:

1. `python.yaml` - Python programming
2. `ai.yaml` - Artificial Intelligence and Machine Learning
3. `gaming.yaml` - Gaming and Game Development
4. `cybersecurity.yaml` - Cybersecurity
5. `data.yaml` - Data and Analytics
6. `coworking.yaml` - Coworking spaces and events
7. `ux-design.yaml` - UX and Design
8. `microsoft.yaml` - Microsoft Technologies
9. `cloud.yaml` - Cloud platforms and services
10. `linux.yaml` - Linux
11. `crypto.yaml` - Cryptocurrency and Blockchain
12. `startups.yaml` - Startups and Business
13. `social.yaml` - Just Social (networking events)
14. `vendor-conferences.yaml` - Vendor Conferences
15. `conferences.yaml` - Conferences (general)
16. `training.yaml` - Training and Workshops

### Deleting Events from iCal Feeds

When an iCal feed contains an event that should not appear on the site, use the soft-delete mechanism in the group's YAML file.

#### Using suppress_urls
For events with known, stable URLs, add the event URL to the `suppress_urls` list in the group's YAML file:

```yaml
# _groups/example-group.yaml
name: "Example Group"
ical: "https://example.com/ical"
suppress_urls:
  - https://example.com/event-to-hide
  - https://another-event-url.com
```

#### Using suppress_guid (New)
For events that recur or don't have stable URLs, suppress by GUID (the unique identifier used in the iCal file and our system):

```yaml
# _groups/example-group.yaml
name: "Example Group"
ical: "https://example.com/ical"
suppress_guid:
  - a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
  - x9y8z7w6v5u4t3s2r1q0p9o8n7m6l5
```

The GUID is the MD5 hash calculated from: `date + time + title + (optional) url`

Both `suppress_urls` and `suppress_guid` can be used together. Events matching either list will be suppressed.

### Using Categories

#### In Single Events
File: `_single_events/{slug}.yaml`

```yaml
title: "Python Meetup"
date: "2024-01-15"
location: "Washington, DC"
# ... other fields ...
categories:
  - python
  - coworking
```

#### In Groups
File: `_groups/{group_slug}.yaml`

```yaml
name: "DC Python Meetup"
website: "https://example.com"
ical: "https://example.com/ical"
# ... other fields ...
categories:
  - python
```

#### In Event Overrides
File: `_event_overrides/{hash}.yaml`

```yaml
title: "Modified Event Title"
location: "New City, DC"
# ... other overridden fields ...
categories:
  - ai
  - data
```

### Category Assignment Logic

1. **Priority**: Event-specific categories override group categories
   - If a single event or override specifies categories, those are used
   - If not specified at event level, inherit from parent group's categories
   - If neither specifies categories, event has no categories

2. **Multiple Categories**: An event can have multiple categories
   - Useful for cross-cutting topics (e.g., a Python AI event → `python` + `ai`)
   - No limit on number of categories per event

3. **Validation**:
   - Category slug must exist in `_categories/` directory
   - Invalid category slugs are either ignored or flagged as errors (TBD during implementation)

### Frontend Display

#### Category Display on Event Listings
- Show category badges/tags inline with events in listings
- Color or styling based on category
- Clickable category links that navigate to category page

#### Category Pages
- New route: `/categories/{slug}/` shows all events in that category
- Uses same template and layout as location pages (location_page.html)
- Page title: "{Category Name} - {count} events"
- Shows category description at top
- Lists all upcoming events in that category, organized by day/time
- Empty state message if no events: "No upcoming events found in {Category Name}. View all events or add an event."
- Includes sitemap generation for SEO

### Backend Implementation

**Note:** This is a statically-built site. All filtering and organization happens during the build process in `generate_month_data.py`, not at request time. Category pages are pre-generated as static HTML files.

#### Loading Categories
- New function `get_categories()` loads all `.yaml` files from `_categories/`
- Returns dict mapping slugs to category metadata
- Loaded during build process

#### Event Data Pipeline

1. **generate_month_data.py** (primary work here):
   - When processing events, resolve categories from both event and group level
   - Store category slugs in event data in `upcoming.yaml`
   - Generate category index data for static category pages
   - Apply `suppress_guid` check (similar to existing `suppress_urls`)

2. **refresh_calendars.py**:
   - When merging iCal events with overrides, preserve category data
   - Inherit group categories for iCal events unless override specifies otherwise
   - No changes needed for suppression (happens in generate_month_data)

3. **app.py**:
   - Add `@app.route("/categories/<slug>/")` route
   - Load pre-generated event data
   - Pass to template for rendering
   - Pass categories context to templates for display

### Data Structure Example

Event in `upcoming.yaml` with categories resolved:

```yaml
- title: "Python AI Meetup"
  date: "2024-01-15"
  time: "18:00"
  location: "Washington, DC"
  url: "https://example.com"
  group: "DC Python Meetup"
  categories:
    - python
    - ai
  source: ical  # or 'manual'
```

## Future Considerations

- Approval workflow for edits (could require organizer confirmation or auto-merge)
- Edit history/audit trail
- Bulk edit capability
- Edit templates for common changes
- Category hierarchy (parent/child categories)
- Category icons/images for visual display
- Auto-categorization based on event title/description keywords
- Personalized category preferences per user
- Category-based email subscriptions
