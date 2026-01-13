# Staging Environment Test Plan (Phase 9.3)

This document provides a step-by-step test plan for validating the deployment to staging environment.

## Pre-Deployment Checklist

- [ ] All code committed and pushed to repository
- [ ] GitHub OAuth app configured with staging domain
- [ ] AWS Secrets Manager has GitHub client secret configured
- [ ] Category files present in `_categories/` directory
- [ ] Environment variables set: AWS_REGION, AWS_SECRETS_NAME, GITHUB_REPO, etc.

## Deployment Steps

1. Deploy code to staging environment
2. Run build process: `python generate_month_data.py`
3. Verify `_data/upcoming.yaml` is generated correctly

## Category Pages Testing

### Test: Category pages load correctly

```bash
# SSH to staging server or access via HTTP
curl -I https://staging.dctech.events/categories/python/
curl -I https://staging.dctech.events/categories/gaming/
curl -I https://staging.dctech.events/categories/ai/
```

Expected: All return HTTP 200

### Test: Category page content displays correctly

1. Navigate to: https://staging.dctech.events/categories/python/
2. Verify:
   - [ ] Page title shows "Python"
   - [ ] Category description displays
   - [ ] Event count shows (e.g., "2 upcoming python events")
   - [ ] Events appear in list organized by day/time
   - [ ] Category badges appear on events

3. Navigate to https://staging.dctech.events/categories/gaming/
4. Verify:
   - [ ] Similar content displays correctly
   - [ ] Different category name and description shown

### Test: Empty category displays correctly

1. Navigate to: https://staging.dctech.events/categories/crypto/
2. If no events in category, verify:
   - [ ] Empty state message displays: "no upcoming crypto events"
   - [ ] Links to home page and event submission form visible

### Test: Category sitemap entries

1. Fetch: https://staging.dctech.events/sitemap.xml
2. Verify:
   - [ ] All 16 category pages listed with `/categories/{slug}/` URLs
   - [ ] Each entry has `<loc>`, `<lastmod>`, and `<changefreq>` tags

## Edit Form Testing

### Test: Edit form loads with pre-populated data

1. Navigate to: https://staging.dctech.events/edit/{event_id}/
   - Replace {event_id} with an actual event GUID or slug from upcoming.yaml
   
2. Verify form displays with:
   - [ ] Event title pre-filled
   - [ ] Event date and time pre-filled
   - [ ] Event location (city/state) pre-filled
   - [ ] Event URL pre-filled
   - [ ] Categories checkboxes checked for event's categories
   - [ ] Source type displayed (ical or manual)
   - [ ] All form fields present and functional

### Test: Form with manual event

1. Find a manual event (source=manual) from upcoming.yaml
2. Navigate to `/edit/{event_slug}/`
3. Verify:
   - [ ] Form loads correctly
   - [ ] "Source: Manual" displayed
   - [ ] Edit would update `_single_events/{slug}.yaml`

### Test: Form with iCal event

1. Find an iCal event (source=ical) from upcoming.yaml
2. Navigate to `/edit/{event_guid}/`
3. Verify:
   - [ ] Form loads correctly
   - [ ] "Source: iCal" displayed
   - [ ] Edit would create `_event_overrides/{guid}.yaml`

## GitHub OAuth Testing

### Test: OAuth flow

1. In edit form, click "Sign in with GitHub" button
2. Browser redirects to GitHub OAuth
3. Approve access (if not already approved)
4. Browser redirects back to edit form
5. Verify:
   - [ ] OAuth token stored in sessionStorage
   - [ ] "Signed in" status shows
   - [ ] Form becomes editable

### Test: Invalid OAuth return URL

1. Attempt to manually create OAuth state with invalid return_url
2. Verify: OAuth endpoint rejects invalid `/other/` paths
3. Verify: Only `/submit/`, `/submit-group/`, and `/edit/{id}/` paths allowed

## PR Creation Testing

### Test: Create edit PR for manual event

1. Load manual event edit form and authenticate with GitHub
2. Make a change (e.g., edit title or add a category)
3. Click "Submit"
4. Verify:
   - [ ] GitHub PR created successfully
   - [ ] PR URL displayed to user
   - [ ] PR branch created: `edit-{event_id}-{timestamp}`
   - [ ] Changes committed to branch
   - [ ] PR description shows diff of changes
   - [ ] File location is `_single_events/{slug}.yaml`

### Test: Create edit PR for iCal event

1. Load iCal event edit form and authenticate with GitHub
2. Make a change (e.g., add cost or description)
3. Click "Submit"
4. Verify:
   - [ ] GitHub PR created successfully
   - [ ] PR shows changes to `_event_overrides/{guid}.yaml`
   - [ ] Override file created in PR
   - [ ] PR description clearly shows what changed

### Test: PR description shows diff clearly

1. After PR created, view the PR on GitHub
2. Verify:
   - [ ] PR title: "Edit event: {event_title}"
   - [ ] PR description shows:
     - Field names that changed
     - Old values
     - New values
     - Example:
       ```
       Changes:
       - title: "Old Title" → "New Title"
       - location: "DC" → "Washington, DC"
       ```

## Data Pipeline Testing

### Test: Sample override file merging

1. Create a test override file: `_event_overrides/{hash}.yaml`
   ```yaml
   title: "Updated Event Title"
   cost: "$25"
   ```

2. Run build process: `python generate_month_data.py`

3. Verify in `_data/upcoming.yaml`:
   - [ ] Event with matching GUID has new title
   - [ ] Event retains all other original fields
   - [ ] Cost field added from override

### Test: Override persists across calendar refresh

1. Note the current title of an iCal event
2. Create override file to change the title
3. Run: `python refresh_calendars.py`
4. Verify:
   - [ ] Override is still applied after refresh
   - [ ] Event shows updated title from override

## Error Handling Testing

### Test: 404 for invalid category

Navigate to: https://staging.dctech.events/categories/invalid/
Verify: Returns HTTP 404 page

### Test: 404 for invalid event

Navigate to: https://staging.dctech.events/edit/invalid-event-id/
Verify: Returns HTTP 404 page

## Performance Testing (Optional)

### Test: Category page load time

Use browser DevTools to measure:
- Page load time (target: < 2 seconds)
- Network requests (target: < 20 requests)
- CSS/JS bundle sizes (should not increase significantly)

## Final Sign-Off

- [ ] All category pages load and display correctly
- [ ] All edit forms load with correct data
- [ ] OAuth flow works end-to-end
- [ ] PR creation succeeds with proper diff
- [ ] Override files merge correctly
- [ ] No errors in application logs
- [ ] Performance is acceptable

Once all tests pass, code is ready for production deployment.

## Rollback Plan

If issues discovered:
1. Revert to previous version in deployment
2. Document issue in GitHub issue
3. Fix in feature branch
4. Re-test on staging before production deployment
