# Agent Guide: dctech.events Architecture

## Core Architecture

**Static Site Generator**: Flask + Frozen-Flask → S3/CloudFront
- Development: Flask dev server (`python app.py`)
- Production: Static HTML/CSS/JS files in `build/`
- Data changes via admin UI trigger automated rebuilds

**Admin/Submit UIs**: HTMX + Cognito Auth
- `suggest.dctech.events` — public event/group submission (Cognito login)
- `manage.dctech.events` — admin dashboard (Cognito `admins` group required)
- Both served as static files from S3/CloudFront

**API Backend**: Lambda + API Gateway
- Returns HTML fragments for HTMX (not JSON)
- Jinja2 server-side templates in `backend/templates/partials/`
- Cognito JWT auth on protected routes

**MCP Server**: Agent-based event database manipulation
- `mcp_server/server.py` — stdio transport, tool registration
- `mcp_server/tools.py` — 16 tools (read/write/history)
- Configured in `.claude/mcp.json`

## Data Storage

### Single DynamoDB Table (`dctech-events`)

All data lives in one table with single-table design. The old `DcTechEvents`
materialized view table is deprecated (kept as backup).

**All events** — iCal, manual, and submitted — are first-class `EVENT#{guid}/META`
entities with GSI keys for efficient querying.

### Config Table Key Patterns

| Entity | PK | SK |
|---|---|---|
| GROUP | `GROUP#{slug}` | `META` |
| CATEGORY | `CATEGORY#{slug}` | `META` |
| EVENT | `EVENT#{guid}` | `META` |
| OVERRIDE | `OVERRIDE#{guid}` | `META` (legacy, being merged into EVENT entities) |
| DRAFT | `DRAFT#{id}` | `META` |
| HISTORY | `EVENT#{guid}` | `V#{iso_timestamp}` |
| ICAL_CACHE | `ICAL#{group_id}` | `EVENT#{guid}` |
| ICAL_META | `ICAL_META#{group_id}` | `META` |

### GSI Patterns

| GSI | PK | SK | Use |
|-----|----|----|-----|
| GSI1 | `DATE#{date}`, `ACTIVE#{0\|1}`, `STATUS#{status}` | `TIME#{time}`, `NAME#{name}`, `{created_at}` | Events by date, groups by active, drafts by status |
| GSI2 | `CATEGORY#{slug}` | `DATE#{date}`, `GROUP#{slug}` | Events/groups by category |
| GSI3 | `USER#{id}`, `CREATED#{YYYY-MM}` | `{created_at}` | User's drafts, recently created events |
| GSI4 | `EVT#ACTIVE` | `{date}#{time}` | **Primary event query**: all future active events by date range |

### Data Access Layer (`dynamo_data.py`)

**Event queries (consolidated):**
- `get_future_events()` → GSI4 query for `EVT#ACTIVE` with SK >= today
- `get_recently_added(limit)` → GSI3 query for `CREATED#{current_month}`
- `put_ical_event(guid, data)` → Write EVENT preserving overridden fields + createdAt

**Config queries:**
- `get_all_groups()`, `get_active_groups()`, `get_all_categories()`
- `get_single_events()`, `get_event_override(guid)`

### Versioned Writes (`versioned_db.py`)

Wiki-style change tracking. Before any mutation, the previous state is
snapshotted as a `V#{iso_timestamp}` sort key under the same PK.

- `versioned_put(pk, item, editor, reason)` — TransactWriteItems: history + update
- `versioned_delete(pk, editor, reason)` — soft-delete with history
- `get_history(pk, limit)` — query V# entries, newest first
- `rollback(pk, version_ts, editor)` — restore snapshot, creates new history entry

## Rebuild Pipeline

### iCal Refresh (decoupled)
EventBridge (every 4h) → iCal Refresh Lambda → writes events to config table

`refresh_calendars.py` fetches iCal feeds, extracts JSON-LD metadata, and writes
`EVENT#{guid}/META` entities directly to the config table. Preserves overridden
fields tracked in the `overrides` map. Same-day events are never removed.

### Site Rebuild
DynamoDB Streams → Dispatcher Lambda → SQS FIFO (60s dedup) → Rebuild Worker Lambda

Rebuild worker runs 4 steps:
1. `npm run build` (esbuild JS assets)
2. `freeze.py` (Frozen-Flask static site from DynamoDB)
3. Sync `build/` to S3
4. CloudFront invalidation

## Cognito Authentication

- **User Pool**: `dctech-events-users`
- **Custom Domain**: `login.dctech.events`
- **Groups**: `admins` (required for manage.dctech.events)
- **OAuth Flow**: Authorization Code with PKCE → token exchange in callback pages
- **Frontend Auth**: `js/auth.js` manages tokens, injects `Authorization` header into HTMX requests

## API Routes (backend/)

### Public
- `GET /health` — health check
- `GET /api/events?date=YYYY-MM` — events by date prefix (HTML table)
- `GET /api/overrides` — list overrides (HTML)

### Authenticated (Cognito JWT)
- `POST /submit` — create draft event/group submission
- `GET /admin/dashboard` — admin stats (HTML fragment)
- `GET /admin/queue` — pending drafts (HTML table rows)
- `POST /admin/draft/{id}/approve` — approve draft
- `POST /admin/draft/{id}/reject` — reject draft
- `GET /admin/groups` — group list (HTML table)
- `GET /admin/groups/{slug}/edit` — group edit form (HTML fragment)
- `PUT /admin/groups/{slug}` — update group
- `GET /admin/events?date=YYYY-MM` — event list from config table (HTML table)
- `GET /admin/overrides` — override list (HTML)

## MCP Server Tools

### Read Tools
- `query_events(date_from, date_to, category, group, search_text, limit)`
- `get_event(guid)` — full detail + recent history
- `list_groups(active_only)` / `get_group(slug)`
- `list_categories()`
- `get_recently_added(limit)`
- `search(query, limit)` — text search across title/description/group/location

### Write Tools (all create versioned history)
- `edit_event(guid, changes, reason)`
- `edit_group(slug, changes, reason)`
- `hide_event(guid, reason)` / `unhide_event(guid, reason)`
- `mark_duplicate(guid, duplicate_of, reason)`
- `set_event_categories(guid, categories, reason)`

### History Tools
- `get_history(entity_type, entity_id, limit)`
- `rollback(entity_type, entity_id, version_timestamp, reason)`

## Infrastructure (CDK)

All stacks in `infrastructure/lib/`:
- `dctech-events-stack.ts` — S3, CloudFront, Route53, DcTechEvents table, GitHub OIDC
- `dynamodb-stack.ts` — Config table with streams, GSI1-4, TTL
- `cognito-stack.ts` — User pool, app client, custom domain, SES email
- `secrets-stack.ts` — Cognito client secret in Secrets Manager
- `rebuild-stack.ts` — Stream dispatcher → SQS FIFO → rebuild worker + iCal refresh Lambda + EventBridge schedule
- `lambda-api-stack.ts` — API Lambda + API Gateway + Cognito authorizer
- `frontend-stack.ts` — S3 + CloudFront + Route53 for suggest/manage subdomains

Entry point: `infrastructure/bin/infrastructure.ts`
Config: `infrastructure/lib/config.ts`

## Static Site Generation

**Frozen-Flask** (`freeze.py`):
- Crawls Flask routes, generates static HTML to `build/`
- Deploy: sync `build/` to S3, invalidate CloudFront

## Development Workflow

1. **Start dev server**: `python app.py`
2. **Test locally**: Visit `http://localhost:5000`
3. **Build for production**: `make freeze`
4. **Deploy infrastructure**: `cd infrastructure && cdk deploy <stack-name>`
5. **Trigger rebuild**: Write any item to `dctech-events` table — stream fires automatically

## File Checklist for Common Tasks

**Add new admin feature**:
- `backend/routes/admin.py` (route handler)
- `backend/templates/partials/` (HTML fragment template)
- `backend/db.py` (DynamoDB operations if needed)
- `frontends/manage/*.html` (admin page with HTMX)

**Add new public submission type**:
- `backend/routes/submit.py` (submission handler)
- `backend/templates/partials/` (form + confirmation templates)
- `frontends/suggest/*.html` (submission page)

**Modify config table schema**:
- `infrastructure/lib/dynamodb-stack.ts` (table definition)
- `backend/db.py` (CRUD operations)
- `dynamo_data.py` (data access layer)
- `migrations/` (migration script if needed)

**Change static generation**:
- `freeze.py` (route generators)
- `app.py` (route logic)
