# DC Tech Events - Copilot Instructions

This is a Flask-based static site generator for aggregating and displaying technology conferences and meetups in and around Washington, DC. The site uses Flask + Frozen-Flask to generate static HTML/CSS/JS files that are deployed to S3/CloudFront. All data changes happen via GitHub Pull Requests - there are no backend writes.

## Architecture Overview

- **Development**: Flask dev server for local testing
- **Production**: Static HTML/CSS/JS files served from S3/CloudFront
- **Data Storage**: YAML files in the repository
- **Edit Workflow**: User edits create GitHub PRs via OAuth
- **Deployment**: GitHub Actions with AWS OIDC (no stored credentials)

## Code Standards

### Required Before Each Commit
- **Python**: Ensure all tests pass with `python -m unittest discover -s . -p "test_*.py"`
- **JavaScript**: Build bundles with `npm run build` before testing
- **YAML**: Validate data files with `make validate`

### Development Flow
- **Install dependencies**: `pip install -r requirements.txt` and `npm install`
- **Build everything**: `make all` (builds JS, refreshes calendars, generates data, freezes site)
- **Run dev server**: `python app.py` (visit http://localhost:5000)
- **Watch JS changes**: `npm run build -- --watch` (in separate terminal)
- **Run tests**: `python -m unittest discover -s . -p "test_*.py"`
- **Run specific test**: `python -m unittest test_app.TestApp.test_name`
- **Test with coverage**: `make test` (runs pytest with coverage)
- **Freeze site**: `make freeze` (generates static HTML in `build/` directory)

### Testing Requirements
- All Python code must have unit tests
- Tests should use the unittest framework (existing pattern)
- Mock external API calls using `unittest.mock` or `responses` library
- Test files follow the pattern `test_*.py`
- Run tests before committing: `python -m unittest discover -s . -p "test_*.py"`

## Repository Structure

### Data Directories
- `_categories/`: Category definitions (16 predefined: python, ai, cybersecurity, etc.)
- `_groups/`: Group/meetup configurations with iCal/RSS feed URLs
- `_single_events/`: Manually submitted single events (format: `YYYY-MM-DD-title.yaml`)
- `_event_overrides/`: Override files for iCal events (merged with base data at build)
- `_data/`: Generated data files (upcoming.yaml) - not committed

### Code Organization
- `app.py`: Flask application with routes and template rendering
- `freeze.py`: Frozen-Flask configuration for static site generation
- `refresh_calendars.py`: Fetches and parses iCal/RSS feeds from groups
- `generate_month_data.py`: Generates upcoming.yaml from events and overrides
- `address_utils.py`: Address parsing utilities (city/state extraction)
- `location_utils.py`: Location handling utilities
- `prune_old_events.py`: Removes old events (7+ days past)

### Frontend
- `templates/`: Jinja2 HTML templates
- `static/css/`: Stylesheets
- `static/js/`: JavaScript ES modules (bundled with esbuild)
- `static/js/dist/`: Built JavaScript bundles (generated, not committed)
- `build.js`: esbuild configuration for bundling

### OAuth Endpoint
- `oauth-endpoint/`: AWS Lambda function for GitHub OAuth callback
- `oauth-endpoint/app.py`: Chalice app handling OAuth flow
- Validates state parameter (CSRF + return URL)
- Allowed return URLs must be whitelisted in code

### Infrastructure
- `infrastructure/`: AWS CDK (TypeScript) for S3, CloudFront, Route53
- `.github/workflows/`: GitHub Actions for CI/CD and automation

## Key Guidelines

### 1. Event Types and File Locations

**CRITICAL**: Always distinguish between manual and iCal events to use correct file paths.

**Manual Events** (`_single_events/*.yaml`):
- User-submitted via web form
- Identified by: `source: 'manual'` and has `id` field
- **Edit directly**: PRs modify the actual file in `_single_events/`
- Filename format: `YYYY-MM-DD-event-title.yaml`

**iCal Events** (imported from feeds):
- Imported from group calendar feeds
- Identified by: `source: 'ical'` and has `guid` field
- **Edit via overrides**: PRs create files in `_event_overrides/{guid}.yaml`
- Override fields merge with base event at render time

### 2. Category Assignment

Categories are assigned as YAML lists:

```yaml
# To a group (all events inherit)
# _groups/python-users.yaml
categories:
  - python
  - data

# To a single event
# _single_events/2026-01-15-event.yaml
categories:
  - python
  - conferences

# Via override file (for iCal events)
# _event_overrides/{guid}.yaml
categories:
  - ai
  - training
```

**Priority**: Event-specific categories override group categories.

### 3. YAML Format Conventions

- **Categories**: Always use YAML list format `categories:\n  - slug\n`
- **Dates**: Use ISO format `YYYY-MM-DD`
- **Times**: Use 24-hour format `HH:MM`
- **Preserve fields**: When updating, preserve existing fields (e.g., `submitted_by`, `suppress_urls`)

### 4. Multi-Day Events with Variable Times

For events spanning multiple days with different times per day:

```yaml
title: Data Center World 2026
date: '2026-04-20'
end_date: '2026-04-23'
time:
  '2026-04-21': '14:00'
  '2026-04-22': '10:00'
  '2026-04-23': '10:00'
```

Days not in the dictionary display as "All Day" events.

### 5. Address Handling

The system extracts city and state only from addresses using the `usaddress` library:
- "1630 7th St NW, Washington, DC 20001" → "Washington, DC"
- "Arlington, VA 22201" → "Arlington, VA"

See `address_utils.py` for implementation.

### 6. JavaScript Build System

**esbuild** bundles ES modules:
- Source files: `static/js/*.js`
- Output: `static/js/dist/*.bundle.js`
- Bundles: submit, submit-group, edit, edit-groups
- Build command: `npm run build`
- Watch mode: `npm run build -- --watch`

Shared utilities in `static/js/github-utils.js`:
- `ensureFork()`: Check/create user's fork
- `createBranch()`: Create branch in fork
- `createOrUpdateFile()`: Commit file changes
- `createPullRequest()`: Create PR to upstream
- `generateCategoryOverride()`: YAML for event overrides
- `updateSingleEventCategory()`: YAML for manual event edits

### 7. Static Site Generation

Frozen-Flask crawls Flask routes and generates static HTML:
- Dynamic routes must be registered via `@freezer.register_generator`
- Output directory: `build/`
- Command: `make freeze` or `python freeze.py`

### 8. OAuth Flow (Client-Side Only)

GitHub OAuth flow for user authentication:
1. User clicks "Sign in with GitHub"
2. JS creates state object: `{csrf_token, return_url, city}`
3. Redirect to GitHub OAuth authorize
4. GitHub redirects to Lambda callback
5. Lambda validates state, exchanges code for token
6. Lambda redirects to return_url with `?access_token=xxx`
7. Client JS stores token in sessionStorage

**Security**:
- State parameter validates CSRF + return URL
- Token stored in sessionStorage (cleared on tab close)
- Lambda validates allowed return URLs (must be whitelisted)

### 9. Edit Workflow Pattern

All edit pages follow this pattern:
1. **Authenticate**: Get GitHub token via OAuth
2. **Fork Check**: Ensure user has fork of `rosskarchner/dctech.events`
3. **Create Branch**: New branch from `main` (e.g., `categorize-events-{timestamp}`)
4. **Modify Files**: Create/update YAML files in user's fork
5. **Create PR**: PR from `user:branch` to `rosskarchner:main`
6. **Show Success**: Display PR URL, allow user to continue editing

### 10. User Interface Messages

- Use inline messages, never `alert()`
- Functions: `showError()`, `showSuccess()`, `showStatus()`
- Messages appear in designated divs in the template

### 11. Deployment

- **Automatic**: GitHub Actions on push to `main`
- **Manual Infrastructure**: `cd infrastructure && npm run cdk deploy`
- **OAuth Endpoint**: `cd oauth-endpoint && chalice deploy`

## Common Tasks

### Add OAuth Return URL
1. Edit `oauth-endpoint/app.py` (add to ALLOWED_RETURN_URLS list)
2. Add test in `oauth-endpoint/test_oauth_app.py`
3. Redeploy: `cd oauth-endpoint && chalice deploy`

### Add New Edit Page
1. Add route in `app.py` with OAuth config
2. Create template in `templates/` with auth UI and message divs
3. Create JS file in `static/js/` with OAuth and PR logic
4. Update `build.js` with esbuild config
5. Register route generator in `freeze.py`
6. Whitelist return URL in `oauth-endpoint/app.py`

### Modify Event Categorization
1. Update YAML utilities in `static/js/github-utils.js`
2. Update template logic in `templates/edit_list.html`
3. Rebuild: `npm run build`

### Change Static Generation
1. Update route generators in `freeze.py`
2. Update route logic in `app.py`

## Important Gotchas

1. **Event Source Detection**: Always check `event.source` before determining file path
2. **YAML Merging**: Preserve existing fields when updating YAML files
3. **OAuth Return URLs**: Must be whitelisted in `oauth-endpoint/app.py` (ALLOWED_RETURN_URLS list)
4. **Category Format**: Always YAML list format, not single value
5. **Fork Wait Time**: Creating fork needs ~3s delay before branch creation
6. **Disable Pagers**: Use `git --no-pager` to avoid interactive output issues

## Testing Strategy

- **Unit Tests**: Use unittest framework
- **Mocking**: Mock external APIs (GitHub, micro.blog, Mastodon, Bluesky)
- **Coverage**: Run `make test` for coverage report
- **Integration**: Test full build with `make all`
- **Manual**: Run dev server and test edit workflows

## Code Review Checklist

Before submitting:
- [ ] All tests pass: `python -m unittest discover -s . -p "test_*.py"`
- [ ] JavaScript builds: `npm run build`
- [ ] YAML files validate: `make validate`
- [ ] No secrets in code
- [ ] User-facing changes have inline messages (not alerts)
- [ ] Event type correctly detected (manual vs iCal)
- [ ] YAML fields preserved when updating

## Documentation

Key reference files:
- `README.md`: User-facing documentation
- `AGENTS.md`: Architecture guide for agents
- `SOCIAL_MEDIA_POSTING.md`: Social media automation
- `EVENT_TRACKING.md`: Event tracking and RSS feed
- `DEPLOYMENT_RUNBOOK.md`: Deployment procedures
- `infrastructure/README.md`: AWS infrastructure setup

## Additional Context

This project emphasizes:
- **Simplicity**: Static site, no database, no server-side sessions
- **Git as CMS**: All edits via PRs, full audit trail
- **User Experience**: Web forms for non-technical users
- **Automation**: GitHub Actions for builds, deployments, and social posts
- **Security**: OAuth for auth, OIDC for AWS, no stored credentials
