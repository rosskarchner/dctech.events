# DC Tech Events - Codebase Guide for AI Agents

This guide provides AI agents with a comprehensive overview of the DC Tech Events codebase structure, architecture, and development workflows.

## Project Overview

**DC Tech Events** is a static site generator that aggregates tech events across the Washington DC/DMV area (DC, Virginia, Maryland). It pulls events from multiple sources (Meetup, Luma, Eventbrite, iCal feeds) and generates a filterable, searchable web interface.

**Tech Stack:**
- **Backend**: Python, Flask, Frozen-Flask
- **Frontend**: JavaScript (esbuild), HTML/CSS
- **Data**: YAML files, iCal/RSS feeds
- **Deployment**: GitHub Actions → GitHub Pages
- **Event Sources**: Meetup.com, lu.ma, Eventbrite, custom iCal feeds

## Repository Structure

```
dctech.events/
├── _groups/                    # 98 YAML files defining tech groups
├── _single_events/             # 35 YAML files for standalone events
├── _data/                      # Generated event data (build artifact)
│   └── upcoming.yaml           # Consolidated event list
├── _cache/                     # Cached iCal/RSS feeds (4-hour TTL)
├── static/                     # Static assets
│   ├── css/                    # Stylesheets
│   └── js/                     # JavaScript source and bundles
│       ├── submit.js           # Event submission form logic
│       ├── submit-group.js     # Group submission form logic
│       └── dist/               # esbuild output (bundled JS)
├── templates/                  # Jinja2 HTML templates
├── .github/workflows/          # CI/CD configuration
│   └── deploy.yml              # Automated build and deployment
├── app.py                      # Main Flask application (900+ lines)
├── refresh_calendars.py        # Fetches events from external sources
├── generate_month_data.py      # Processes and deduplicates events
├── freeze.py                   # Static site generation
├── build.js                    # esbuild configuration
├── Makefile                    # Build orchestration
├── config.yaml                 # Site configuration
├── requirements.txt            # Python dependencies
├── package.json                # Node.js dependencies
├── ADD_EVENTS.md              # Guide for adding events (see below)
└── AGENTS.md                  # This file
```

## Data Flow and Build Pipeline

### High-Level Architecture

```
Source Data (YAML files)
         ↓
Event Fetching (refresh_calendars.py)
         ↓
Event Processing (generate_month_data.py)
         ↓
Consolidated Data (_data/upcoming.yaml)
         ↓
Flask Application (app.py)
         ↓
Static Site Generation (freeze.py)
         ↓
Deployment (GitHub Pages)
```

### Detailed Build Process

1. **Data Sources** (`_groups/`, `_single_events/`)
   - Tech groups with iCal or RSS feeds
   - Individual events in YAML format
   - See [ADD_EVENTS.md](./ADD_EVENTS.md) for details on adding events

2. **Event Fetching** (`refresh_calendars.py`)
   - Fetches iCal files from group configurations
   - Parses RSS feeds (with JSON-LD extraction)
   - Caches responses for 4 hours to minimize API calls
   - Normalizes addresses and timezones (US/Eastern)
   - Key function: `normalize_address()` for location standardization

3. **Event Processing** (`generate_month_data.py`)
   - Consolidates events from all sources
   - Deduplicates based on title + date + time
   - Filters events within 50 miles of DC center
   - Extracts location metadata (city, state)
   - Outputs to `_data/upcoming.yaml`

4. **Flask Application** (`app.py`)
   - Renders templates with Jinja2
   - Routes: `/`, `/locations/{state}/{city}`, `/week/{id}`, `/groups/`, `/submit/`, etc.
   - Loads configuration from `config.yaml`
   - Provides development server for local testing

5. **Static Generation** (`freeze.py`)
   - Uses Frozen-Flask to convert dynamic routes to static HTML
   - Generates pages for all locations, weeks, and submission forms
   - Output directory: `build/`

6. **JavaScript Bundling** (`build.js`)
   - esbuild bundles `submit.js` and `submit-group.js`
   - Minification and sourcemaps enabled
   - Output to `static/js/dist/`

### Build Commands

```bash
make clean                  # Remove build artifacts
make js-build              # Bundle JavaScript with esbuild
make refresh-calendars     # Fetch event data from sources
make generate-month-data   # Process and consolidate events
make freeze                # Generate static site
make all                   # Run complete build pipeline
make validate              # Run validation checks
```

## Key Files and Components

### Core Python Scripts

#### app.py (Flask Application)
- **Purpose**: Main web application and routing
- **Key Routes**:
  - `/` - Homepage with all events
  - `/locations/` - Regional filtering (DC, VA, MD)
  - `/locations/{state}/{city}` - City-specific pages
  - `/week/{week_id}` - Weekly event views
  - `/groups/` - List of tech groups
  - `/submit/`, `/submit-group/` - Event/group submission forms
- **Templates**: Uses Jinja2 templates from `templates/` directory
- **Configuration**: Loads from `config.yaml`

#### refresh_calendars.py (Event Fetcher)
- **Purpose**: Fetch events from iCal and RSS sources
- **Key Features**:
  - 4-hour caching system (stores in `_cache/`)
  - HTTP ETag support for efficient fetching
  - RSS feed parsing with JSON-LD extraction
  - iCal parsing with `icalendar` library
  - Timezone handling (converts to US/Eastern)
- **Functions**:
  - `fetch_ical()` - Downloads and parses iCal feeds
  - `fetch_rss()` - Fetches RSS feeds and extracts event data
  - `normalize_address()` - Standardizes location strings

#### generate_month_data.py (Event Processor)
- **Purpose**: Consolidate and deduplicate events
- **Key Features**:
  - Merges data from iCal, RSS, and single events
  - Deduplication algorithm (title + date + time matching)
  - Location parsing and validation
  - Distance filtering (50-mile radius from DC)
  - YAML output generation
- **Functions**:
  - `parse_events()` - Processes event data from all sources
  - `deduplicate_events()` - Removes duplicate entries
  - `filter_by_distance()` - Geographic filtering

#### freeze.py (Static Site Generator)
- **Purpose**: Convert Flask app to static HTML
- **Uses**: Frozen-Flask library
- **URL Generators**: Dynamic functions for routes
- **Output**: `build/` directory with deployable site

### Utility Modules

- **location_utils.py**: Extracts city/state from addresses using regex
- **address_utils.py**: Normalizes and cleans address strings
- **config.yaml**: Site configuration (name, timezone, OAuth credentials)

### Frontend JavaScript

#### static/js/submit.js
- Event submission form logic
- GitHub OAuth integration via Octokit
- Creates pull requests with new event YAML files

#### static/js/submit-group.js
- Group submission form logic
- Similar OAuth workflow for adding tech groups
- Creates PRs to `_groups/` directory

### Data Formats

#### Group Configuration (_groups/*.yaml)

**iCal-based group:**
```yaml
name: Tech Group Name
website: https://example.com
ical: https://example.com/calendar.ics
fallback_url: https://example.com/events
active: true
```

**RSS-based group (Meetup):**
```yaml
name: Meetup Group Name
website: https://www.meetup.com/group-name/
rss: https://www.meetup.com/group-name/events/rss/
active: true
```

#### Single Event (_single_events/*.yaml)

```yaml
title: "Event Title"
date: '2025-06-15'           # YYYY-MM-DD format, quoted
time: '18:30'                # HH:MM 24-hour format, quoted
end_date: '2025-06-15'       # Optional
end_time: '20:00'            # Optional
url: https://event-url.com
location: 'Venue Name, Street, City, State'
cost: null                   # null for free, or string like "$25"
submitted_by: username
submitter_link: https://profile.com
```

**Filename convention:** `YYYY-MM-DD-{slugified-title}.yaml`

## Event Management

For detailed instructions on adding events, see **[ADD_EVENTS.md](./ADD_EVENTS.md)**.

### Quick Reference

**Add events with scripts:**
```bash
python add-luma.py https://lu.ma/event-slug
python add-eventbrite.py https://www.eventbrite.com/e/event-id
```

**Add groups:**
```bash
python add_meetup.py          # Interactive, for Meetup groups
python add_group.py           # Interactive, for any group
```

**Manual file creation:**
- Single events: Create YAML in `_single_events/`
- Groups: Create YAML in `_groups/`

See [ADD_EVENTS.md](./ADD_EVENTS.md) for complete documentation.

## Development Workflow

### Local Development Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   npm install
   ```

2. **Run development server:**
   ```bash
   flask run --debug
   ```
   Visit http://localhost:5000

3. **Build static site:**
   ```bash
   make all
   ```

### Testing Changes

```bash
# Clean previous builds
make clean

# Run individual steps
make js-build              # Bundle JavaScript
make refresh-calendars     # Fetch latest events
make generate-month-data   # Process event data
make freeze                # Generate static site

# Or run complete pipeline
make all
```

### Adding New Events or Groups

1. **Automated (recommended):**
   - Use the appropriate script (`add-luma.py`, `add-eventbrite.py`, etc.)
   - Scripts create properly formatted YAML files

2. **Manual:**
   - Create YAML file in `_single_events/` or `_groups/`
   - Follow naming conventions and required fields
   - See [ADD_EVENTS.md](./ADD_EVENTS.md) for details

3. **Web submission:**
   - Use `/submit/` or `/submit-group/` forms
   - Requires GitHub OAuth
   - Creates PR automatically

4. **Test locally:**
   ```bash
   make all
   flask run --debug
   ```

5. **Commit and push:**
   - Changes trigger GitHub Actions
   - Automated build and deployment to GitHub Pages

## CI/CD Pipeline

### GitHub Actions Workflow (.github/workflows/deploy.yml)

**Triggers:**
- Manual dispatch
- Push to main branch
- Daily schedule at 2 AM Eastern (6 AM UTC)

**Steps:**
1. Checkout repository
2. Set up Python 3.10 and Node.js 20
3. Cache dependencies and data (4-hour cache)
4. Install Python and npm packages
5. Run `make all` (full build pipeline)
6. Deploy to GitHub Pages

**Environment Variables:**
- `GITHUB_CLIENT_ID` - OAuth for submission forms (set in repo variables)

### Caching Strategy

- **Event data**: 4-hour cache in `_cache/` directory
- **Dependencies**: Cached between CI runs
- **Build artifacts**: Regenerated on each deployment

## Common Tasks for AI Agents

### Adding a Single Event

1. Check if event platform is supported (Luma, Eventbrite)
2. If supported, use appropriate script:
   ```bash
   python add-luma.py <event-url>
   ```
3. If not supported, create YAML file manually in `_single_events/`
4. Validate YAML syntax and required fields
5. Test with `make all && flask run --debug`

### Adding a Tech Group

1. Determine if group has iCal or RSS feed
2. Use `add_meetup.py` for Meetup groups, `add_group.py` for others
3. Or create YAML manually in `_groups/`
4. Ensure `active: true` is set
5. Test to verify events are fetched correctly

### Debugging Event Issues

**Event not appearing:**
- Check `_data/upcoming.yaml` after running `make generate-month-data`
- Verify event date is in the future
- Check location is within 50-mile radius
- Look for duplicate detection (title + date + time match)

**Group events not fetching:**
- Check `_cache/` directory for cached feed data
- Verify feed URL is accessible
- Check `refresh_calendars.py` output for errors
- Ensure `active: true` in group YAML

**Build failures:**
- Check YAML syntax validity
- Verify all required fields are present
- Look for import/dependency errors in Python scripts
- Check esbuild output for JavaScript errors

### Modifying Core Functionality

**Adding a new event source:**
1. Create a script in root (e.g., `add-platform.py`)
2. Extract structured data (JSON-LD preferred)
3. Parse to YAML format matching schema
4. Add to `_single_events/` or create group in `_groups/`

**Changing event filtering:**
- Modify `generate_month_data.py`
- Update distance filter, duplicate logic, or location parsing
- Test with diverse event data

**Adding new routes:**
1. Add route decorator in `app.py`
2. Create corresponding template in `templates/`
3. Add URL generator in `freeze.py` for static generation
4. Test both Flask dev server and frozen build

## Important Constraints and Considerations

### Geographic Filtering
- Events must be within 50 miles of DC center point
- Location parsing expects "Venue, Street, City, State" format
- Use "Online" for virtual events

### Time Zones
- All times are interpreted as US/Eastern
- The build system handles timezone conversion
- Store times in 'HH:MM' 24-hour format

### Deduplication
- Events matched on: title + date + time
- Slight variations create separate entries
- Check for duplicates when adding similar events

### Caching
- 4-hour cache for external feeds
- Minimizes API calls and build times
- Clear `_cache/` directory to force refresh

### YAML Format
- Dates and times must be quoted strings
- Use single quotes: `'2025-06-15'` not `2025-06-15`
- Boolean values: `true`/`false` (lowercase, unquoted)
- Null values: `null` (unquoted)

## File Locations Quick Reference

| Task | Files | Location |
|------|-------|----------|
| Add single event | `YYYY-MM-DD-slug.yaml` | `_single_events/` |
| Add tech group | `group-slug.yaml` | `_groups/` |
| View consolidated events | `upcoming.yaml` | `_data/` |
| Modify templates | `*.html` | `templates/` |
| Edit frontend logic | `submit.js`, etc. | `static/js/` |
| Configure build | `Makefile`, `build.js` | Root |
| CI/CD configuration | `deploy.yml` | `.github/workflows/` |
| Site configuration | `config.yaml` | Root |

## Dependencies

### Python (requirements.txt)
- Flask - Web framework
- Frozen-Flask - Static site generation
- PyYAML - YAML parsing
- icalendar - iCal feed parsing
- feedparser - RSS feed parsing
- requests - HTTP requests
- extruct - JSON-LD extraction
- dateparser - Date parsing
- pytz - Timezone handling

### Node.js (package.json)
- esbuild - JavaScript bundling
- @octokit/core - GitHub API integration

## Resources

- **Event Addition Guide**: [ADD_EVENTS.md](./ADD_EVENTS.md)
- **Repository**: https://github.com/rosskarchner/dctech.events
- **Deployment**: GitHub Pages (automated via Actions)

## Summary

This codebase is a **data-driven static site generator** that:
1. Aggregates events from 98+ tech groups and individual submissions
2. Processes and deduplicates event data
3. Generates a searchable, filterable website
4. Deploys automatically via GitHub Actions
5. Accepts community contributions via web forms or direct YAML edits

The architecture prioritizes:
- **Automation**: Scripts for common platforms
- **Caching**: Minimize external API calls
- **Validation**: Ensure data quality
- **Simplicity**: YAML files as source of truth
- **Community**: Easy contribution via web or PR

For adding events, always refer to **[ADD_EVENTS.md](./ADD_EVENTS.md)** for current procedures and examples.
