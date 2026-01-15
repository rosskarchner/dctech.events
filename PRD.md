# Category Management and Filtering Features - PRD

## Overview
Implement three features following existing patterns from `/edit` and `/groups/edit`:
1. New `/categories/edit` page for category CRUD operations
2. Filtering on `/edit/` page (uncategorized events, manual-only events)
3. Filtering on `/groups/edit/` page (uncategorized groups)

## Feature 1: /categories/edit Page

### Backend
- [x] Add `/categories.json` endpoint in `app.py` (after line 1103)
  - Convert categories dict to list format
  - Include slug, name, description for each category
- [x] Add `/categories/edit/` route in `app.py` (after line 1120)
  - Pass categories, OAuth config, dev mode flag
  - Render `edit_categories.html` template

### Frontend Template
- [x] Create `templates/edit_categories.html`
  - [x] Copy OAuth authentication section from `edit_groups.html`
  - [x] Add categories list view showing name, slug (badge), description
  - [x] Add "Create New Category" button at top
  - [x] Add Edit/Delete action buttons for each category
  - [x] Create edit/create modal with fields:
    - Name (text input, required)
    - Description (textarea, optional)
    - Slug (read-only display for edits, auto-shown for creates)
  - [x] Create delete confirmation modal with usage stats
  - [x] Add status overlay for GitHub operations
  - [x] Add success modal with PR link
  - [x] Add CSS styles matching edit_groups.html pattern
  - [x] Add inline JavaScript to inject OAuth config and categories data

### Frontend JavaScript
- [x] Create `static/js/edit-categories.js`
  - [x] Implement `loadCategories()` - fetch from `/categories.json`
  - [x] Implement `renderCategoriesList()` - display categories
  - [x] Implement `slugify(text)` - convert name to slug (lowercase, hyphenated)
  - [x] Implement `openCreateModal()` - show modal for new category
  - [x] Implement `openEditModal(slug)` - show modal with existing data, slug read-only
  - [x] Implement `createCategory(name, description)`:
    - Generate slug from name
    - Check for duplicate slug, show error if exists
    - Create YAML file at `_categories/{slug}.yaml`
    - Create PR with proper title/body
  - [x] Implement `editCategory(slug, newName, newDescription)`:
    - Preserve slug (read-only)
    - Update name and description only
    - Update YAML file
    - Create PR
  - [x] Implement `deleteCategory(slug)`:
    - Fetch `/events.json` and `/groups.json`
    - Count usage in events and groups
    - Show confirmation modal with stats
    - Allow deletion (don't block)
    - Create PR with usage stats in body
  - [x] Implement modal handlers (show/hide, form submission)
  - [x] Implement YAML generation with proper escaping
  - [x] Add OAuth initialization and GitHub API integration

### Build Configuration
- [x] Add webpack build script for `edit-categories.bundle.js`
- [x] Update package.json or webpack config with new entry point
- [x] Build and verify bundle generation

## Feature 2: Filtering on /edit Page

### Backend
- [x] Update `edit_list()` route in `app.py` (line 1010)
  - [x] Calculate `events_without_categories` count
  - [x] Calculate `manual_events_count`
  - [x] Calculate `ical_events_count`
  - [x] Pass `filter_stats` dict to template

### Frontend Template
- [x] Update `templates/edit_list.html`
  - [x] Add filter controls section (after line 36, after auth section):
    - "Show only events without categories" checkbox
    - "Show only manual events (hide iCal)" checkbox
    - "Clear Filters" button
    - Filtered status message span
  - [x] Add CSS styles for filter controls (in existing `<style>` block):
    - `.filter-controls` container styling
    - `.filter-count` badge styling
    - `.filtered-status` message styling
    - `.time-slot-group.filtered-out` hide rule
  - [x] Update event checkbox template to add `data-event-categories` attribute
  - [x] Add JavaScript filter logic (in existing `<script type="module">` block):
    - [x] Add `activeFilters` state object
    - [x] Update `showAuthenticatedState()` to show filter controls and setup handlers
    - [x] Implement `setupFilterHandlers()` for checkbox changes and clear button
    - [x] Implement `applyFilters()`:
      - Iterate through time slot groups and event rows
      - Apply noCategories filter (hide if has categories)
      - Apply manualOnly filter (hide if source !== 'manual')
      - Use AND logic for combined filters
      - Hide time slots with no visible events
      - Update filtered status message

## Feature 3: Filtering on /groups/edit Page

### Backend
- [x] Update `edit_groups()` route in `app.py` (line 1105)
  - [x] Load groups with `get_approved_groups()`
  - [x] Calculate `groups_without_categories` count
  - [x] Pass `filter_stats` dict to template

### Frontend Template
- [ ] Update `templates/edit_groups.html`
  - [ ] Add filter controls section (after line 58, after category controls):
    - "Show only groups without categories" checkbox
    - "Clear Filter" button
    - Filtered status message span
  - [ ] Add CSS styles for filter controls (in existing `<style>` block):
    - `.filter-controls` container styling
    - `.filter-count` badge styling
    - `.filtered-status` message styling
    - `.group-row.filtered-out` hide rule

### Frontend JavaScript
- [ ] Update `static/js/edit-groups.js`
  - [ ] Add `filterNoCategories` state variable
  - [ ] Update `showAuthenticatedState()` to show filter controls and setup handlers
  - [ ] Implement `setupFilterHandlers()` for checkbox change and clear button
  - [ ] Implement `applyFilter()`:
    - Iterate through group rows
    - Check if group has categories
    - Hide/show based on filter state
    - Update filtered status message
  - [ ] Update `renderGroupsList()` to call `applyFilter()` after rendering

## Implementation Guidelines

### Key Rules
- [ ] Category slug is auto-generated from name via `slugify()` during creation
- [ ] Category slug is YAML filename without extension
- [ ] Category slug is READ-ONLY after creation (cannot be edited)
- [ ] Only name and description are editable for existing categories
- [ ] Filters reset on page reload (no localStorage persistence)
- [ ] Multiple filters use AND logic
- [ ] Delete allows deletion with warning (doesn't block)

## Testing & Verification

### Category Management
- [ ] Navigate to `/categories/edit` and authenticate with GitHub
- [ ] Create new category "Test Category"
  - [ ] Verify PR created with `_categories/test-category.yaml`
  - [ ] Verify slug auto-generated correctly
- [ ] Edit existing category (name and description only)
  - [ ] Verify PR updates file correctly
  - [ ] Verify slug remains unchanged
- [ ] Attempt to create duplicate category
  - [ ] Verify error message shown
- [ ] Delete unused category
  - [ ] Verify PR deletes file
- [ ] Assign category to events/groups, then delete
  - [ ] Verify warning modal shows usage counts
  - [ ] Verify deletion is allowed
  - [ ] Verify PR body includes usage stats

### Event Filtering
- [ ] Navigate to `/edit/` and authenticate
- [ ] Verify filter controls appear with correct counts
- [ ] Enable "Show only events without categories"
  - [ ] Verify only uncategorized events visible
  - [ ] Verify time slots with no matches are hidden
  - [ ] Verify count shows correctly
- [ ] Enable "Show only manual events"
  - [ ] Verify iCal events hidden
  - [ ] Verify only manual events visible
- [ ] Enable both filters
  - [ ] Verify AND logic works correctly
  - [ ] Verify status message shows correct count
- [ ] Clear filters
  - [ ] Verify all events reappear
- [ ] Reload page
  - [ ] Verify filters reset to unchecked

### Group Filtering
- [ ] Navigate to `/groups/edit/` and authenticate
- [ ] Enable "Show only groups without categories"
  - [ ] Verify only uncategorized groups visible
  - [ ] Verify status message shows correct count
- [ ] Clear filter
  - [ ] Verify all groups reappear
- [ ] Reload page
  - [ ] Verify filter resets

### Edge Cases
- [ ] Test special characters in category names (emojis, unicode, punctuation)
- [ ] Test very long category names (>100 chars)
- [ ] Test empty description handling
- [ ] Test deleting categories used by many events/groups (50+)
- [ ] Test filtering with 0 matches
- [ ] Test concurrent PR conflicts

### Browser Testing
- [ ] Test in Chrome
- [ ] Test in Firefox
- [ ] Test in Safari
- [ ] Test mobile responsive layouts
- [ ] Check JavaScript console for errors
- [ ] Check Network tab for API call issues

## Files Summary

### New Files
- `templates/edit_categories.html`
- `static/js/edit-categories.js`
- `static/js/dist/edit-categories.bundle.js` (generated)

### Modified Files
- `app.py` (add routes at lines 1103, 1120; update routes at lines 1010, 1105)
- `templates/edit_list.html` (add filter controls, CSS, JavaScript)
- `templates/edit_groups.html` (add filter controls, CSS)
- `static/js/edit-groups.js` (add filter logic)
- Build config (package.json or webpack config)
