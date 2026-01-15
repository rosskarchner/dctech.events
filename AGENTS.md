# Agent Guide: dctech.events Architecture

## Core Architecture

**Static Site Generator**: Flask + Frozen-Flask → S3/CloudFront
- Development: Flask dev server
- Production: Static HTML/CSS/JS files
- All data changes via GitHub Pull Requests (no backend writes)

## Data Storage

All content stored as YAML files in the repository:

### Events (Two Types)
1. **Manual Events** (`_single_events/*.yaml`)
   - User-submitted via web form
   - Identified by: `source: 'manual'`, has `id` field
   - **Edit directly**: PRs modify the actual file in `_single_events/`

2. **iCal Events** (imported from feeds)
   - Imported from group calendar feeds
   - Identified by: `source: 'ical'`, has `guid` field
   - **Edit via overrides**: PRs create files in `_event_overrides/{guid}.yaml`
   - Override fields merge with base event at render time

### Groups (`_groups/*.yaml`)
- One file per group (e.g., `_groups/tech-meetup.yaml`)
- Contains: name, website, ical feed URL, categories, active status
- **Edit directly**: PRs modify the actual group file

### Categories (`_categories/*.yaml`)
- 16 predefined categories (ai, cybersecurity, etc.)
- Rarely changed

## GitHub OAuth Flow

**Client-Side Only** - No backend session management

### Architecture
- **OAuth App**: GitHub OAuth App (Client ID: `Ov23liSTVbSKSvkYW6yg`)
- **Lambda Endpoint**: `/auth/callback` (AWS Lambda via Chalice)
  - Source: `oauth-endpoint/app.py`
  - Validates `state` parameter (CSRF token + return URL)
  - Allowed return URLs: `/submit/`, `/submit-group/`, `/groups/edit/`, `/edit/*`
  - Exchanges code for access token
  - Redirects to return URL with `?access_token=xxx`

### Client Flow
1. User clicks "Sign in with GitHub"
2. JS creates state object: `{csrf_token, return_url, city}`
3. Redirect to `https://github.com/login/oauth/authorize`
4. GitHub redirects to Lambda callback
5. Lambda validates state, exchanges code for token
6. Lambda redirects to return_url with `?access_token=xxx`
7. Client JS stores token in `sessionStorage`, initializes Octokit

### Security
- State parameter validates CSRF + return URL
- Token stored in sessionStorage (cleared on tab close)
- Lambda validates allowed return URLs to prevent open redirects

## Edit Workflows

### Common Pattern (All Edit Pages)
1. **Authenticate**: Get GitHub token via OAuth
2. **Fork Check**: Ensure user has fork of `rosskarchner/dctech.events`
3. **Create Branch**: New branch from `main` (e.g., `categorize-events-1234567890`)
4. **Modify Files**: Create/update YAML files in user's fork
5. **Create PR**: PR from `user:branch` to `rosskarchner:main`
6. **Show Success**: Display PR URL, allow user to continue editing

### Event Categorization (`/edit/`)
**Key Logic** (`templates/edit_list.html:909`):
```javascript
if (event.source === 'manual' && event.id) {
    // Manual event: Edit _single_events/{id}.yaml directly
    filePath = `_single_events/${event.id}.yaml`;
} else {
    // iCal event: Create override in _event_overrides/{guid}.yaml
    filePath = `_event_overrides/${eventId}.yaml`;
}
```

**Critical**: Must distinguish between manual and iCal events to use correct file path!

### Group Editing (`/groups/edit/`)
Two modes:
1. **Bulk Categorization**: Select multiple groups, assign category
2. **Individual Edit**: Modal form to edit all group fields

Both create PRs modifying `_groups/*.yaml` files directly (no override mechanism).

## JavaScript Build System

**esbuild** bundles ES modules:
- Source: `static/js/*.js`
- Output: `static/js/dist/*.bundle.js`
- Bundles: `submit`, `submit-group`, `edit`, `edit-groups`
- Run: `npm run build` (or `npm run build -- --watch`)

### Shared Utilities (`static/js/github-utils.js`)
- `ensureFork()` - Check/create user's fork
- `createBranch()` - Create branch in fork
- `createOrUpdateFile()` - Commit file changes
- `createPullRequest()` - Create PR to upstream
- `generateCategoryOverride()` - YAML for event overrides
- `updateSingleEventCategory()` - YAML for manual event edits

## Static Site Generation

**Frozen-Flask** (`freeze.py`):
- Crawls Flask routes and generates static HTML
- Must register dynamic routes via `@freezer.register_generator`
- Output: `build/` directory
- Deploy: Sync to S3, invalidate CloudFront cache

## Development Workflow

1. **Start dev server**: `python app.py`
2. **Watch JS changes**: `npm run build -- --watch` (separate terminal)
3. **Test locally**: Visit `http://localhost:5000`
4. **Build for production**:
   - `npm run build` (JS bundles)
   - `make freeze` (static HTML)
5. **Deploy**: Sync `build/` to S3

## OAuth Endpoint Deployment

Separate Lambda function in `oauth-endpoint/`:
1. **Test**: `pytest test_app.py`
2. **Deploy**: `chalice deploy`
3. **Update allowed URLs**: Edit `app.py` line 81, redeploy

## Key Gotchas

1. **Event Source Detection**: Always check `event.source` before determining file path
2. **YAML Merging**: Preserve existing fields when updating (e.g., `submitted_by`, `suppress_urls`)
3. **OAuth Return URLs**: Must be whitelisted in `oauth-endpoint/app.py:81`
4. **Category Format**: Always YAML list format: `categories:\n  - slug\n`
5. **Fork Wait Time**: Creating fork needs ~3s delay before branch creation
6. **Inline Messages**: Use `showError()`, `showSuccess()`, `showStatus()` - never `alert()`

## File Checklist for Common Tasks

**Add OAuth return URL**:
- `oauth-endpoint/app.py` (line 81)
- `oauth-endpoint/test_app.py` (add test)
- Redeploy: `chalice deploy`

**Add new edit page**:
- `app.py` (route + OAuth config)
- `templates/your-page.html` (auth UI + message divs)
- `static/js/your-page.js` (OAuth + PR logic)
- `build.js` (esbuild config)
- `freeze.py` (register generator)
- `oauth-endpoint/app.py` (whitelist return URL)

**Modify event categorization**:
- `static/js/github-utils.js` (YAML utilities)
- `templates/edit_list.html` (inline script)
- Rebuild: `npm run build`

**Change static generation**:
- `freeze.py` (route generators)
- `app.py` (route logic)
