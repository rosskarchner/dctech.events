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

## Data Storage

### Two DynamoDB Tables

1. **`dctech-events` (config/admin table)** — Single-table design
   - Source of truth for groups, categories, overrides, drafts
   - Changes trigger site rebuilds via DynamoDB Streams
   - Managed by admin UI and data access layer

2. **`DcTechEvents` (materialized event view)** — Existing table
   - Written by `generate_month_data.py` (fetches iCal feeds, deduplicates)
   - Read by `app.py` to render the static site

### Config Table Key Patterns

| Entity | PK | SK |
|---|---|---|
| GROUP | `GROUP#{slug}` | `META` |
| CATEGORY | `CATEGORY#{slug}` | `META` |
| EVENT | `EVENT#{guid}` | `META` |
| OVERRIDE | `OVERRIDE#{guid}` | `META` |
| DRAFT | `DRAFT#{id}` | `META` |
| ICAL_CACHE | `ICAL#{group_id}` | `EVENT#{guid}` |
| ICAL_META | `ICAL_META#{group_id}` | `META` |

Three GSIs: GSI1 (GSI1PK/GSI1SK), GSI2 (GSI2PK/GSI2SK), GSI3 (GSI3PK/GSI3SK).

### Data Access Layer (`dynamo_data.py`)

Reads from the config table, provides same interfaces as the old YAML reads:
- `get_all_groups()`, `get_all_categories()`, `get_single_events()`, `get_event_override(guid)`
- Feature flag: `USE_DYNAMO_DATA=1` enables DynamoDB reads; defaults to YAML fallback for local dev

## Rebuild Pipeline

DynamoDB Streams → Dispatcher Lambda → SQS FIFO (60s dedup window) → Docker Rebuild Worker Lambda

1. Config table change triggers stream event
2. `lambdas/stream_dispatcher/handler.py` sends SQS message with `DeduplicationId = floor(epoch/60)`
3. `lambdas/rebuild_worker/handler.py` runs full rebuild:
   - Sync cache from S3 → refresh calendars → generate month data → freeze → sync to S3 → CloudFront invalidation

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
- `GET /admin/overrides` — override list (HTML)

## Infrastructure (CDK)

All stacks in `infrastructure/lib/`:
- `dctech-events-stack.ts` — S3, CloudFront, Route53, DcTechEvents table, GitHub OIDC
- `dynamodb-stack.ts` — Config table with streams, GSIs, TTL
- `cognito-stack.ts` — User pool, app client, custom domain, SES email
- `secrets-stack.ts` — Cognito client secret in Secrets Manager
- `rebuild-stack.ts` — Stream dispatcher → SQS FIFO → Docker rebuild worker
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
