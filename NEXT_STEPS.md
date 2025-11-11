# Multi-City Extension Plan for dctech.events → localtech.events

## Phase 1: Repository Restructuring
1. **Create new directory structure:**
   - `cities/dc/_groups/` - Move existing `_groups/` here
   - `cities/dc/_single_events/` - Move existing `_single_events/` here
   - `cities/dc/_data/` - Move existing `_data/` here
   - `cities/dc/sponsors.yaml` - New sponsor config file
   - Delete root `_groups/`, `_single_events/`, `_data/` after migration

2. **Update config.yaml:**
   - Add `cities` array with DC as first entry (slug: dc, name: Washington DC, timezone: US/Eastern)
   - Keep existing root-level config for dctech.events defaults
   - Add `GITHUB_SPONSORS_TOKEN` to required env vars

## Phase 2: Core Code Changes
3. **Update data processing scripts:**
   - `location_utils.py`: Remove hardcoded DC/VA/MD state filtering
   - `refresh_calendars.py`: Accept `--city` parameter, read from `cities/{slug}/_groups/`
   - `generate_month_data.py`: Accept `--city` parameter, output to `cities/{slug}/_data/`

4. **Create GitHub Sponsors integration:**
   - New `fetch_sponsors.py`: Query GitHub GraphQL API for sponsor verification
   - Reads `cities/{slug}/sponsors.yaml` (list of usernames)
   - Outputs `cities/{slug}/_data/sponsors.json` with avatar URLs
   - 4-hour cache like calendar fetching

5. **Update Flask application (app.py):**
   - Add `--city` CLI parameter to specify which city to build
   - Load city config from `config.yaml` cities array
   - Remove region-based routing for non-DC builds (no /locations/va/, /locations/md/)
   - Load sponsors from `cities/{slug}/_data/sponsors.json`
   - Update context processor with city-specific values
   - Add root homepage route (only for localtech.events builds)

6. **Create localtech.events homepage:**
   - New template `templates/city_index.html`
   - Lists all cities from config.yaml with links to subdomains
   - Shows total event count across all cities
   - Links to GitHub repo for adding new cities
   - Styled to match existing dctech.events aesthetic

7. **Update templates:**
   - Modify `base.html` navigation to be city-aware (no VA/MD links for non-DC)
   - Create `templates/partials/sponsors.html` for sidebar
   - Update all templates to use dynamic city config

8. **Update freeze.py:**
   - Accept `--city` parameter for city-specific builds
   - Accept `--homepage` flag for localtech.events homepage build
   - Output to `build/{city-slug}/` for city sites
   - Output to `build/` for homepage or dctech.events

## Phase 3: AWS Infrastructure (CDK)
9. **Create CDK stack in `infrastructure/` directory:**
   - S3 bucket: `localtech-events-hosting` with structure:
     - `/index.html` (homepage)
     - `/{city-slug}/index.html` (city sites)
   - CloudFront distribution with CloudFront Functions for routing:
     - `localtech.events` → `/index.html` (homepage)
     - `{city}.localtech.events` → `/{city}/index.html`
   - ACM certificate for `*.localtech.events` and `localtech.events` (us-east-1)
   - Route53 records in `localtech.events` hosted zone:
     - A/AAAA alias for `localtech.events` → CloudFront
     - A/AAAA alias for `*.localtech.events` → CloudFront
   - Origin Access Control for S3 bucket security

10. **CDK implementation files:**
    - `infrastructure/package.json` - TypeScript + AWS CDK dependencies
    - `infrastructure/tsconfig.json` - TypeScript config
    - `infrastructure/cdk.json` - CDK config
    - `infrastructure/bin/app.ts` - CDK app entry point
    - `infrastructure/lib/localtech-stack.ts` - Main stack definition
    - `infrastructure/lib/origin-request-function.js` - CloudFront Function for routing

## Phase 4: CI/CD Updates
11. **Keep existing GitHub Actions:**
    - `deploy.yml` - Update to build from `cities/dc/`, continues deploying to GitHub Pages

12. **New GitHub Actions workflows:**
    - `deploy-localtech.yml`:
      - Trigger: push to main, daily cron
      - Build homepage (no --city flag, --homepage flag)
      - Build all cities in `cities/*/` (loop with `--city` flag)
      - Sync all to S3 bucket with appropriate paths
      - Invalidate CloudFront cache
    - `deploy-infrastructure.yml`:
      - Trigger: changes to `infrastructure/**` or manual dispatch
      - Run CDK deploy with AWS credentials from GitHub Secrets

13. **Update OAuth endpoint:**
    - Modify Lambda function to detect city from referer/origin header
    - Parse subdomain from `https://{city}.localtech.events/submit/`
    - Create PR targeting `cities/{city}/_single_events/` or `cities/{city}/_groups/`
    - Fallback to DC if city not detected

## Phase 5: Build System Updates
14. **Update Makefile:**
    - Add `CITY` variable (defaults to `dc`)
    - Update all targets to use `cities/$(CITY)/`
    - Add `make homepage` target for localtech.events homepage
    - Keep existing `make all` working for DC/dctech.events

15. **Update package.json scripts:**
    - Keep existing build working
    - Add convenience script for multi-city builds

## Phase 6: Testing & Validation
16. **Create example second city** (e.g., `cities/sf/` with minimal test data)
17. **Update documentation:**
    - README.md with multi-city architecture overview
    - CITIES.md guide for adding new cities
    - INFRASTRUCTURE.md for AWS CDK deployment instructions

## Key Technical Decisions
- **No symlinks**: Direct path updates in scripts, better cross-platform compatibility
- **Build-time city selection**: Scripts accept `--city` flag to build specific cities
- **Homepage at apex domain**: localtech.events shows city directory, subdomains show cities
- **Route53 managed**: Full DNS automation in CDK stack
- **CloudFront Functions**: Lightweight subdomain-to-path routing
- **Backward compat**: dctech.events unchanged, builds from `cities/dc/`
- **Sponsor verification**: GitHub GraphQL API during build, cached 4 hours

## Final Directory Structure
```
dctech.events/
├── cities/
│   ├── dc/
│   │   ├── _groups/ (120+ files)
│   │   ├── _single_events/ (40+ files)
│   │   ├── _data/ (generated)
│   │   └── sponsors.yaml
│   └── sf/ (example)
│       ├── _groups/
│       ├── _single_events/
│       ├── _data/
│       └── sponsors.yaml
├── infrastructure/
│   ├── bin/app.ts
│   ├── lib/
│   │   ├── localtech-stack.ts
│   │   └── origin-request-function.js
│   ├── package.json
│   └── cdk.json
├── .github/workflows/
│   ├── deploy.yml (updated)
│   ├── deploy-localtech.yml (new)
│   ├── deploy-infrastructure.yml (new)
│   └── deploy-oauth.yml (updated)
├── config.yaml (cities array added)
├── fetch_sponsors.py (new)
├── app.py (city-aware + homepage route)
├── freeze.py (city-aware + homepage flag)
├── refresh_calendars.py (city-aware)
├── generate_month_data.py (city-aware)
├── templates/
│   ├── city_index.html (new - homepage)
│   └── partials/sponsors.html (new)
└── NEXT_STEPS.md (this plan)
```

## URLs After Implementation
- `localtech.events` → Homepage listing all cities
- `dc.localtech.events` → Washington DC events
- `sf.localtech.events` → San Francisco events (example)
- `dctech.events` → Continues working via GitHub Pages (unchanged)
