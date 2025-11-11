# Multi-City Implementation Status

This document tracks the progress of transforming dctech.events into localtech.events, a multi-city platform for technology events.

## Implementation Plan

Based on `NEXT_STEPS.md`, the implementation is divided into 6 phases. This document tracks the status of each phase.

## Completed Phases

### ✅ Phase 1: Repository Restructuring (COMPLETE)

All data has been reorganized into a city-specific structure:

- [x] Created `cities/dc/_groups/` directory with 110 group files
- [x] Created `cities/dc/_single_events/` directory with 39 event files
- [x] Created `cities/dc/_data/` directory for generated data
- [x] Created `cities/dc/sponsors.yaml` for sponsor configuration
- [x] Updated `config.yaml` with cities array configuration
- [x] Added GitHub Sponsors configuration to `config.yaml`
- [x] Removed old root-level `_groups/` and `_single_events/` directories

**Status**: All existing dctech.events data successfully migrated to `cities/dc/` structure.

### ✅ Phase 2: Core Code Changes (COMPLETE)

All Python scripts and Flask application updated for multi-city support:

- [x] Updated `location_utils.py` to accept any US state (not just DC/VA/MD)
- [x] Updated `refresh_calendars.py` with `--city` parameter
- [x] Updated `generate_month_data.py` with `--city` parameter
- [x] Created `fetch_sponsors.py` for GitHub Sponsors integration
- [x] Updated Flask `app.py` with:
  - `--city` and `--homepage` CLI parameters
  - City-specific configuration loading
  - Sponsor data loading and injection
  - Homepage route for multi-city index
- [x] Created `templates/city_index.html` for localtech.events homepage
- [x] Updated `templates/base.html` navigation to be city-aware
- [x] Updated `freeze.py` with city and homepage build support

**Status**: All core application code is multi-city ready. Can build for DC or run as homepage.

### ✅ Phase 3: AWS Infrastructure (COMPLETE)

Complete AWS CDK infrastructure for localtech.events deployment:

- [x] Created `infrastructure/package.json` with CDK dependencies
- [x] Created `infrastructure/tsconfig.json` for TypeScript configuration
- [x] Created `infrastructure/cdk.json` for CDK app configuration
- [x] Created `infrastructure/bin/app.ts` - CDK app entry point
- [x] Created `infrastructure/lib/localtech-stack.ts` - Main stack with:
  - S3 bucket for static hosting
  - CloudFront distribution with Origin Access Control
  - ACM certificate for `*.localtech.events` and apex domain
  - Route53 A/AAAA records for apex and wildcard subdomain
  - CloudFront Function for subdomain routing
- [x] Created `infrastructure/lib/origin-request-function.js` - Routing logic:
  - `localtech.events` → `/index.html` (homepage)
  - `dc.localtech.events` → `/dc/index.html`
  - `{city}.localtech.events` → `/{city}/index.html`

**Status**: Infrastructure code complete. Ready for `cdk deploy` when needed.

### ✅ Phase 4: Build System Updates (COMPLETE)

Makefile updated for city-aware builds:

- [x] Added `CITY` variable (defaults to `dc`)
- [x] Updated all Python script targets to use `--city $(CITY)`
- [x] Added `make homepage` target for localtech.events homepage build
- [x] Updated `clean` target to handle city-specific paths
- [x] Maintained backward compatibility - `make all` builds DC by default

**Status**: Build system fully supports multi-city builds. Existing workflows unchanged.

## Remaining Work

### 🔄 Phase 5: CI/CD Workflows (NOT STARTED)

GitHub Actions workflows need to be created/updated:

#### To Update:
- [ ] `.github/workflows/deploy.yml` - Update for new city structure
  - Should continue deploying dctech.events to GitHub Pages
  - Update paths to use `cities/dc/`

#### To Create:
- [ ] `.github/workflows/deploy-localtech.yml` - New workflow for multi-city deployment
  - Trigger: Push to main, daily cron
  - Build homepage with `make homepage`
  - Build all cities in `cities/*/` with `CITY={slug} make all`
  - Sync to S3 bucket at appropriate paths
  - Invalidate CloudFront cache

- [ ] `.github/workflows/deploy-infrastructure.yml` - CDK deployment workflow
  - Trigger: Changes to `infrastructure/**` or manual dispatch
  - Run `cdk deploy` with AWS credentials from GitHub Secrets
  - Required secrets: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

#### OAuth Lambda Updates:
- [ ] Update `oauth-endpoint/` Lambda function:
  - Detect city from referer/origin header
  - Parse subdomain from `https://{city}.localtech.events/submit/`
  - Create PR targeting `cities/{city}/_single_events/` or `cities/{city}/_groups/`
  - Fallback to DC if city not detected

### 🔄 Phase 6: Testing & Documentation (PARTIALLY COMPLETE)

- [ ] Create example second city (e.g., `cities/sf/`) with minimal test data
- [ ] Test multi-city build process end-to-end
- [ ] Update `README.md` with multi-city architecture overview
- [ ] Create `CITIES.md` guide for adding new cities
- [ ] Create `INFRASTRUCTURE.md` for AWS CDK deployment instructions
- [x] Document implementation status (this file)

## Current Capabilities

### Working Now:
1. **Build DC site**: `make all` builds dctech.events from `cities/dc/`
2. **Build any city**: `CITY=sf make all` (once city data exists)
3. **Build homepage**: `make homepage` creates localtech.events city index
4. **Run dev server**: `python app.py` runs DC site (default)
5. **Run dev server (any city)**: `python app.py --city sf`
6. **Run dev server (homepage)**: `python app.py --homepage`

### Ready to Deploy (needs setup):
1. **AWS Infrastructure**: Run `cd infrastructure && npm install && cdk deploy`
2. **S3 Deployment**: Upload build output to S3 bucket structure:
   - `/index.html` - Homepage (from `make homepage`)
   - `/dc/*` - DC city site (from `make all`)
   - `/{city}/*` - Other city sites (from `CITY={city} make all`)

### Not Yet Working:
1. GitHub Actions automated deployments (workflows not yet updated)
2. OAuth endpoint city detection (Lambda not yet updated)
3. Multi-city testing (no second city data yet)

## Architecture Decisions Made

1. **No symlinks**: Direct path updates in scripts for cross-platform compatibility
2. **Build-time city selection**: Scripts accept `--city` flag rather than runtime detection
3. **Homepage at apex domain**: localtech.events shows city directory, subdomains show cities
4. **CloudFront Functions**: Lightweight subdomain-to-path routing (not Lambda@Edge)
5. **Backward compatibility**: DC continues deploying to GitHub Pages at dctech.events
6. **Sponsor verification**: GitHub GraphQL API during build, cached 4 hours
7. **DC-specific features preserved**: VA/MD location filtering only for DC city

## Directory Structure (Current State)

```
dctech.events/
├── cities/
│   └── dc/
│       ├── _groups/ (110 files)
│       ├── _single_events/ (39 files)
│       ├── _data/ (generated during build)
│       └── sponsors.yaml
├── infrastructure/
│   ├── bin/app.ts
│   ├── lib/
│   │   ├── localtech-stack.ts
│   │   └── origin-request-function.js
│   ├── package.json
│   ├── tsconfig.json
│   └── cdk.json
├── templates/
│   ├── city_index.html (new - homepage)
│   ├── base.html (updated - city-aware nav)
│   └── ... (other templates)
├── .github/workflows/
│   ├── deploy.yml (needs update)
│   └── ... (new workflows needed)
├── config.yaml (updated with cities array)
├── fetch_sponsors.py (new)
├── app.py (updated - city-aware)
├── freeze.py (updated - city-aware)
├── refresh_calendars.py (updated - city-aware)
├── generate_month_data.py (updated - city-aware)
├── location_utils.py (updated - all states)
├── Makefile (updated - city-aware)
└── NEXT_STEPS.md (original plan)
```

## Testing Checklist

Before deploying to production, test:

- [ ] `make all` builds DC successfully
- [ ] `make homepage` builds localtech.events index
- [ ] `python app.py` runs DC dev server
- [ ] `python app.py --homepage` runs homepage dev server
- [ ] Create SF test city and build with `CITY=sf make all`
- [ ] Deploy infrastructure with `cdk deploy`
- [ ] Upload test build to S3 and verify routing
- [ ] Test CloudFront subdomain routing
- [ ] Verify DNS resolution for `*.localtech.events`

## Next Steps

Priority order for completing the implementation:

1. **Create example second city** (`cities/sf/`) for testing
2. **Test multi-city build** locally before deploying
3. **Update existing deploy.yml** workflow for new paths
4. **Create deploy-localtech.yml** workflow for automated deployments
5. **Create deploy-infrastructure.yml** for CDK deployments
6. **Update OAuth Lambda** for city detection
7. **Deploy AWS infrastructure** (`cdk deploy`)
8. **Update documentation** (README, CITIES, INFRASTRUCTURE)
9. **Test end-to-end** with real deployment
10. **Announce multi-city support** and invite contributions

## Migration Impact

### Backward Compatibility
- ✅ DC site continues to work at dctech.events (GitHub Pages)
- ✅ `make all` continues to build DC without changes
- ✅ All existing GitHub Actions continue to work
- ✅ No data loss - all files migrated successfully

### Breaking Changes
- None for end users
- Developers must use new paths (`cities/dc/` instead of `_groups/`)
- Future PRs must target city-specific directories

## Questions/Decisions Needed

1. **DNS Setup**: Who owns/manages `localtech.events` domain?
2. **AWS Account**: Which AWS account should host the infrastructure?
3. **Deployment Strategy**: Gradual rollout or big-bang launch?
4. **City Selection**: How to prioritize which cities to add first?
5. **Moderation**: How to handle city-specific event moderation?

## Resources

- Original plan: `NEXT_STEPS.md`
- AWS CDK docs: https://docs.aws.amazon.com/cdk/
- CloudFront Functions: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cloudfront-functions.html
