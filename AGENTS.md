# Gemini CLI Configuration (GEMINI.md)

This project is a static site generator (Python) with a serverless backend (Lambda, API Gateway, DynamoDB) and an HTMX-based frontend (S3, CloudFront, Cognito).

## System Architecture

**Static Site**: Python + Jinja2 + Makefile
- Data: `_data/` (groups, locations), `_event_overrides/` (one-off event edits)
- Build: `make build` (generates HTML in `build/`)
- Production: Static HTML/CSS/JS files in `build/`
- Data changes via admin UI trigger automated rebuilds

**Admin/Submit UIs**: HTMX + Cognito Auth
- `edit.dctech.events` — consolidated frontend for public event/group submission and admin management. (Replaces `suggest.dctech.events` and `manage.dctech.events`)
- Served from S3 via the unified `edit.dctech.events` CloudFront distribution

**API Backend**: Lambda + API Gateway
- Returns HTML fragments for HTMX (not JSON)
- Cognito authorizer for protected routes
- DynamoDB for events, groups, and categories

**Database (DynamoDB)**:
- Table: `DcTechEvents` (Single-table design)
- Key: `eventId` (PK)
- Indices: `DateIndex`, `CreatedIndex`

## Workflows

### 1. Modifying Frontend Pages
- Primary location: `frontends/edit/`
- All pages use HTMX and Cognito Auth (`frontends/edit/js/auth.js`)
- Pages: `index.html` (Dashboard), `submit-event.html` (Public), `queue.html` (Admin), etc.

### 2. Modifying Backend API
- Primary location: `backend/`
- `backend/handler.py`: Entry point for Lambda
- `backend/routes/`: Route handlers (e.g., `submit.py`, `admin.py`, `public.py`)
- `backend/templates/partials/`: HTML fragments returned by the API

### 3. Modifying Infrastructure (CDK)
- Primary location: `infrastructure/`
- `infrastructure/lib/`: Stack definitions
- `infrastructure/lib/config.ts`: Shared configuration and constants

## Project Standards

1. **Keep it Simple**: Prioritize simple, readable Python and clean HTML over complex abstractions.
2. **HTMX Over JSON**: Always return HTML fragments from the API for the admin and submit UIs.
3. **No NPM/Build Step for JS**: Use vanilla JS and unpkg for HTMX/other libraries.
4. **Surgical Changes**: When modifying existing code, only touch what is necessary.
5. **Security First**: Never log or expose secrets. All protected routes must have Cognito authorizers.
