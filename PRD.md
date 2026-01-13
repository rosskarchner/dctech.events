# Implementation Plan for New Features

## Overview
This document outlines the step-by-step implementation of two major features:
1. Event Edit Functionality (GitHub PR workflow)
2. Event Categorization System

## Phase 1: Foundation - Categories Infrastructure

### - [x] 1.1 Create Categories Directory Structure
**Files to Create:**
- `_categories/python.yaml`
- `_categories/ai.yaml`
- `_categories/gaming.yaml`
- `_categories/cybersecurity.yaml`
- `_categories/data.yaml`
- `_categories/coworking.yaml`
- `_categories/ux-design.yaml`
- `_categories/microsoft.yaml`
- `_categories/cloud.yaml`
- `_categories/linux.yaml`
- `_categories/crypto.yaml`
- `_categories/startups.yaml`
- `_categories/social.yaml`
- `_categories/vendor-conferences.yaml`
- `_categories/conferences.yaml`
- `_categories/training.yaml`

**Content Template:**
```yaml
name: "Category Name"
description: "Human-readable description of this category"
```

**Estimated effort:** 2 hours (create 15 category files with appropriate names and descriptions)

### - [x] 1.2 Add `get_categories()` Function
**File:** `app.py`

**Changes:**
- Create new `get_categories()` function similar to `get_approved_groups()`
- Load all `.yaml` files from `_categories/` directory
- Returns dict mapping slugs to category metadata: `{'python': {'name': '...', 'description': '...', 'icon': '...'}, ...}`
- Implement caching/lazy-loading
- Add to context processor with `@app.context_processor` so categories available in all templates

**Estimated effort:** 1 hour

### - [x] 1.3 Add suppress_guid Feature
**File:** `_groups/{group_id}.yaml` (per-group configuration)

**Changes:**
- Add new optional field `suppress_guid` to group YAML files (similar to `suppress_urls`)
- Works same way as `suppress_urls` but matches against the event GUID (MD5 hash)
- Allows suppressing events that don't have stable URLs or recur

**Example:**
```yaml
name: "Example Group"
ical: "https://example.com/ical"
suppress_urls:
  - https://example.com/event-url
suppress_guid:
  - a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
  - x9y8z7w6v5u4t3s2r1q0p9o8n7m6l5
```

**Implementation in generate_month_data.py:**
- When processing iCal events, check both `suppress_urls` and `suppress_guid`
- Skip event if URL matches `suppress_urls` OR GUID matches `suppress_guid`

**Estimated effort:** 1 hour

### - [x] 1.4 Update Data Loading Pipeline
**Files:**
- `generate_month_data.py`
- `refresh_calendars.py`

**Changes in generate_month_data.py:**
- Load categories at start of build process
- When building `upcoming.yaml`, resolve categories for each event:
  - Check if event has `categories` field → use those
  - Else check if event's group has `categories` field → inherit those
  - Else event has no categories
- Store resolved categories in event data in `upcoming.yaml`
- Apply `suppress_guid` check when processing iCal events (alongside existing `suppress_urls` check)

**Changes in refresh_calendars.py:**
- When merging iCal event with override file, preserve category from override
- If override doesn't specify categories but group has them, inherit group categories
- No changes needed for suppression (handled by generate_month_data)

**Estimated effort:** 2-3 hours

---

## Phase 2: Category Pages

### - [x] 2.1 Create Category Page Template
**File:** `templates/category_page.html`

**Template Structure:**
- Extend `base.html`
- Display category name as title
- Show category description
- Display count of upcoming events
- Include `partials/events_by_day.html` to show events organized by day/time
- Show empty state if no events
- Add OG meta tags for social sharing

**Note:** Can be largely copy-pasted from `location_page.html` with variable names changed

**Estimated effort:** 1 hour

### - [x] 2.2 Add Category Page Route
**File:** `app.py`

**Changes:**
- Add new route: `@app.route("/categories/<slug>/")`
- Function: `category_page(slug)`
- Validate slug exists in categories
- Filter events by category
- Call `prepare_events_by_day(filtered_events)`
- Render with `category_page.html` template
- Pass: `days`, `stats` (with `upcoming_events` count), `category_name`, `category_description`

**Code Pattern (based on region_page):**
```python
@app.route("/categories/<slug>/")
def category_page(slug):
    """Show events for a specific category"""
    categories = get_categories()
    if slug not in categories:
        return "Category not found", 404
    
    events = get_events()
    filtered_events = [e for e in events if slug in e.get('categories', [])]
    days = prepare_events_by_day(filtered_events)
    
    category = categories[slug]
    stats = {'upcoming_events': len(filtered_events)}
    
    return render_template('category_page.html',
                         days=days,
                         stats=stats,
                         category_name=category['name'],
                         category_description=category['description'])
```

**Estimated effort:** 1 hour

### - [x] 2.3 Update Sitemap Generation
**File:** `app.py` (in `sitemap()` function)

**Changes:**
- Add loop to include all category pages in sitemap
- Generate URLs like `{base_url}/categories/{slug}/`
- Set `changefreq` to 'daily' (like location pages)

**Estimated effort:** 30 minutes

### - [x] 2.4 Test Category Pages
**Testing:**
- Verify each category page loads without errors
- Verify filtering logic (only shows events with that category)
- Verify empty state displays correctly
- Verify sitemap includes category pages

**Estimated effort:** 1 hour

---

## Phase 3: Edit Functionality - Backend Infrastructure

### - [x] 3.1 Create `_event_overrides/` Directory
**Changes:**
- Create empty `_event_overrides/` directory
- Add to `.gitignore` (if override files shouldn't be committed) OR leave tracked (if they should be)
- **Decision needed:** Should override files be committed to git or generated dynamically?

**Estimated effort:** 15 minutes

### - [x] 3.2 Add Event Hash Calculation Utility
**File:** `app.py` (or new `event_utils.py`)

**Function:** `calculate_event_hash(date, time, title, url=None)`

**Implementation:**
- Match the logic from iCal GUID generation (lines 1110-1123)
- Input: date (YYYY-MM-DD), time (HH:MM or ''), title, optional url
- Output: MD5 hash string
- Should be deterministic (same inputs always produce same hash)

```python
def calculate_event_hash(date, time, title, url=None):
    """
    Calculate MD5 hash for event identification.
    Matches iCal GUID generation algorithm.
    
    Args:
        date: Event date (YYYY-MM-DD format)
        time: Event time (HH:MM format, or empty string)
        title: Event title
        url: Optional event URL
    
    Returns:
        MD5 hash string (hex)
    """
    uid_parts = [date, time, title]
    if url:
        uid_parts.append(url)
    
    uid_base = '-'.join(str(p) for p in uid_parts)
    uid_hash = hashlib.md5(uid_base.encode('utf-8')).hexdigest()
    return uid_hash
```

**Estimated effort:** 30 minutes

### - [x] 3.3 Update Event Loading in generate_month_data.py (PRIMARY)
**File:** `generate_month_data.py`

**Changes:**
- When building events from iCal feeds:
  - Calculate event hash (date + time + title + optional url)
  - Check if `_event_overrides/{hash}.yaml` exists
  - If exists, load and merge it with iCal event data (override fields take precedence)
  - Store merged event in `upcoming.yaml`
- For manual events from `_single_events/`:
  - Load and include as-is (or merged with override if it exists)
  - Store in `upcoming.yaml`
- Store original event source indicator in event data ('ical' or 'manual')
- Ensure categories are assigned/inherited correctly

**Estimated effort:** 2 hours

---

## Phase 4: Edit Functionality - UI and Forms

### - [x] 4.1 Create Edit Form Template
**File:** `templates/edit.html`

**Template Structure:**
- Extend `base.html` (similar to `submit.html` layout)
- Display GitHub auth status and login button
- Hidden edit form (shown after authentication)
- Form fields (pre-populated with current event data):
  - Title (required, text input)
  - Date (required, date picker)
  - Time (optional, time picker)
  - Location (required, text input with validation)
  - URL (optional, text input with URL validation)
  - Cost (optional, text input)
  - Group (display-only, not editable)
  - Categories (checkboxes for available categories)
  - Description (optional, textarea)
  - Any other fields from event data
- Note indicating "source is locked and cannot be changed"
- Submit button
- Success page with PR link (shown after form submission)
- Pass GitHub OAuth config to JavaScript via `window.GITHUB_CONFIG`

**Estimated effort:** 2-3 hours

### - [ ] 4.2 Create Frontend JavaScript for Edit Form
**File:** `static/js/edit.js`

**Functionality:**
- Initialize GitHub OAuth (same pattern as `submit.js`)
- Check for OAuth token in URL and store in sessionStorage
- Show/hide auth section and form based on authentication state
- Pre-populate form fields with event data
- Implement client-side location validation (City, State format)
- Handle form submission:
  - Validate all fields
  - Prepare diff for PR description
  - Generate event hash (same as iCal GUID calculation)
  - Determine file path based on event type (manual vs override)
  - Use Octokit to create GitHub PR via front-end code
- Show success page with PR link on success
- Show error messages on failure

**Key differences from submit.js:**
- Load pre-populated event data (passed from Flask)
- Generate PR description with diff showing changes
- For iCal events: create file in `_event_overrides/{hash}.yaml`
- For manual events: update file in `_single_events/{slug}.yaml`

**Estimated effort:** 2.5 hours

### - [ ] 4.3 Test Forms Locally
**Testing:**
- Load edit form for different event types (manual vs iCal)
- Verify form pre-population
- Verify location validation works
- Verify GitHub OAuth flow
- Test PR creation with front-end code

**Estimated effort:** 1 hour

---

## Phase 5: Edit Functionality - Backend (Minimal)

### - [ ] 5.1 Add `/edit/<event_id>/` Route
**File:** `app.py`

**Function:** `edit_event(event_id)`

**Logic:**
1. Load event data from `upcoming.yaml` (pre-generated during build)
   - Determine if event_id is a slug (manual event) or hash (iCal event)
   - Find matching event in `upcoming.yaml`
2. Pass event data to template as JSON via `window.EVENT_DATA`
3. Pass GitHub OAuth config to JavaScript via `window.GITHUB_CONFIG`
4. Render `edit.html` template

**Note:** No authentication check needed - edit button only shown to logged-in users in frontend

**Estimated effort:** 1 hour

### - [ ] 5.2 Add Event Hash Calculation Utility
**File:** `app.py` (shared utility)

**Function:** `calculate_event_hash(date, time, title, url=None)`

**Implementation:**
- Match iCal GUID generation logic (lines 1110-1123)
- Used by `generate_month_data.py` during build to identify iCal events
- Exposed to JavaScript via template context for use in `edit.js`

**Estimated effort:** 30 minutes

---

## Phase 6: GitHub Integration (Frontend-based)

### - [ ] 6.1 Review Existing GitHub OAuth Flow
**Files:** `oauth-endpoint/`, `.github/workflows/deploy-oauth.yml`, `static/js/submit.js`

**Tasks:**
- Verify existing OAuth callback endpoint works
- Understand Octokit usage pattern in submit.js
- Confirm repo config and permissions are sufficient for edit PRs
- No backend changes needed - all PR creation done via front-end

**Estimated effort:** 1 hour (review only)

### - [ ] 6.2 Implement PR Creation in edit.js
**File:** `static/js/edit.js`

**Function:** `createEditPullRequest(eventType, eventId, formData, originalEvent)`

**Logic (all front-end, using Octokit):**
1. Initialize Octokit with GitHub token from sessionStorage
2. Generate PR title and description:
   - Title: `Edit event: {event_title}`
   - Description: Formatted diff of changes
3. Determine target file:
   - Manual events: `_single_events/{slug}.yaml`
   - iCal events: `_event_overrides/{hash}.yaml`
4. Build YAML content from form data
5. Use Octokit to:
   - Create branch from main: `edit-{event-id}-{timestamp}`
   - Commit file changes to branch
   - Create pull request
   - Return PR URL
6. Display success page with PR link

**Pattern:** Same as `submit.js` but for editing existing events

**Estimated effort:** 2 hours

---

## Phase 7: Integration and Data Flow Updates

### - [ ] 7.1 Ensure Override and Category Merging in Data Pipeline
**Files:** `generate_month_data.py`, `refresh_calendars.py`

**Tasks:**
- Verify overrides are loaded and merged when building `upcoming.yaml`
- Verify categories are assigned and inherited correctly
- Verify `suppress_guid` suppresses events correctly
- Test with sample override files

**Estimated effort:** 1-2 hours

### - [ ] 7.2 Update Tests
**Files:**
- `test_app.py` - add tests for new routes
- `test_generate_month_data.py` - test override merging
- Create new test file if needed

**Test cases:**
- Category page loads correctly
- Event filtering by category works
- Edit form loads with correct data
- Override file creation works
- Location validation works
- Hash calculation is deterministic

**Estimated effort:** 3-4 hours

### - [ ] 7.3 Integration Testing
**Testing:**
- End-to-end: create manual event → edit it → verify changes in PR
- End-to-end: iCal event → edit it → verify override file created → verify it appears in listings
- Verify categories are assigned correctly through pipeline
- Test with multiple categories per event
- Test empty states (no events in category, no overrides)

**Estimated effort:** 2-3 hours

---

## Phase 8: Frontend Polish and Documentation

### - [ ] 8.1 Update Templates for Categories
**Files:**
- `templates/partials/events_by_day.html` - display category badges on events

**Changes:**
- Add category badges to event listings (inline with event)
- Show category names with links to `/categories/{slug}/`
- Use consistent styling across templates

**Estimated effort:** 1-2 hours

### - [ ] 8.2 Update README.md
**File:** `README.md`

**Add sections:**
- Directory structure (mention `_categories/`, `_event_overrides/`)
- How to add events to a category
- How to edit events (steps, links to edit page)
- Category system explanation

**Estimated effort:** 1 hour

### - [ ] 8.3 Update QUICK_REFERENCE.md
**File:** `QUICK_REFERENCE.md`

**Add:**
- Category file format and location
- How to assign categories to events/groups
- How to edit events via web interface

**Estimated effort:** 30 minutes

---

## Phase 9: Deployment and Monitoring

### - [ ] 9.1 Prepare Deployment
**Tasks:**
- Ensure all new directories exist (or are created on first run)
- Test locally in all environments (dev, staging)
- Review all file paths for correctness
- Verify GitHub OAuth is configured correctly

**Estimated effort:** 1-2 hours

### - [ ] 9.2 Create Initial Categories (Post-Deploy)
**Task:**
- After code is deployed, populate `_categories/` with initial 15 categories
- Or commit category YAML files in Phase 1

**Estimated effort:** 30 minutes

### - [ ] 9.3 Test on Staging
**Tasks:**
- Deploy code to staging environment
- Test category pages load correctly
- Test edit form with real GitHub OAuth
- Test PR creation with real GitHub API
- Create sample override file and test in data pipeline

**Estimated effort:** 2-3 hours

---

## Implementation Order and Dependencies

### Critical Path (Minimum for MVP)
1. Phase 1.1-1.4: Categories infrastructure (including suppress_guid)
2. Phase 3.1-3.3: Event override loading in build process
3. Phase 4.1-4.2: Edit form template and frontend JavaScript
4. Phase 5.1-5.2: Minimal backend (route + hash utility)
5. Phase 6.1-6.2: Frontend GitHub PR creation (Octokit)
6. Phase 2.1-2.4: Category pages (simpler, can be done anytime after 1.4)
7. Phase 7.1-7.3: Integration and testing

### Suggested Sequence by Sprint
**Sprint 1 (Categories Infrastructure):**
- 1.1, 1.2, 1.3, 1.4, 2.1-2.4
- Output: Category system fully working, suppress_guid feature added, category pages live

**Sprint 2 (Edit Foundation):**
- 3.1-3.3, 4.1-4.2, 5.1-5.2
- Output: Event override loading working, edit form template ready, backend route ready

**Sprint 3 (Edit Frontend + GitHub Integration):**
- 6.1-6.2, 4.3
- Output: Full edit flow working with frontend PR creation via Octokit

**Sprint 4 (Testing + Deployment):**
- 7.1-7.3, 8.1-8.3, 9.1-9.3
- Output: Production-ready, tested, deployed

---

## Estimated Total Effort

| Phase | Estimated Hours |
|-------|-----------------|
| 1. Categories Infrastructure | 6.5 |
| 2. Category Pages | 4 |
| 3. Edit Infrastructure | 2 |
| 4. Edit UI and Forms | 5.5 |
| 5. Edit Backend (Minimal) | 1.5 |
| 6. GitHub Integration (Frontend) | 2 |
| 7. Integration & Testing | 8 |
| 8. Frontend Polish & Docs | 3.5 |
| 9. Deployment & Monitoring | 5 |
| **TOTAL** | **~38 hours** |

---

## Decisions Made

1. ✅ **Override File Storage:** Committed to git via PR workflow (same as new submissions)
2. ✅ **Category Icons:** Skipped for now (future consideration)
3. ✅ **Event Detail Pages:** No individual detail pages - events only in listings, links go to primary sources
4. ✅ **Auto-categorization:** Not implemented now (recorded as future consideration)
5. ✅ **Category Hierarchy:** Flat structure only
6. ✅ **Soft Delete Implementation:** Use `suppress_urls` (existing) and add new `suppress_guid` feature in group YAML
7. ✅ **GitHub PR Auto-Merge:** Out of scope - all PRs require manual review
8. ✅ **Performance:** N/A - site is statically built, no real-time features or caching needed

---

## Testing Checklist

- [x] Categories load correctly from `_categories/` directory
- [x] Category pages filter events properly
- [x] Category pages appear in sitemap
- [ ] suppress_guid suppresses events from iCal feeds
- [ ] suppress_urls and suppress_guid work together
- [x] Categories assigned from groups are inherited by events
- [ ] Categories in event/override override group categories
- [ ] Edit form displays with pre-populated data
- [ ] Location validation works (client and server)
- [ ] Category checkboxes work on edit form
- [ ] Manual events can be edited
- [ ] iCal events create override files
- [ ] Override files merge correctly during build
- [ ] GitHub PR creation succeeds
- [ ] PR description shows diff clearly
- [ ] Edit button only shows for authenticated users
- [ ] Overrides persist across calendar refreshes
- [ ] Multiple categories per event works
- [x] Empty state displays correctly on category pages
- [ ] Category badges display on events in listings
