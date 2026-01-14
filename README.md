# DC Tech Events

A platform for aggregating and displaying technology conferences and meetups in and around Washington, DC.

## 🚀 Quick Start

### Prerequisites

- Python 3.10+ with pip
- Node.js 20+ with npm

### Local Development

1. **Install dependencies**:

```bash
pip install -r requirements.txt
npm install
```

2. **Build and run**:

```bash
make all          # Build everything
python app.py     # Start dev server
```

3. **Visit** `http://localhost:5000`

## 📁 Directory Structure

```
_categories/         # Category definitions (python.yaml, ai.yaml, etc.)
_data/               # Generated data files (upcoming.yaml)
_event_overrides/    # Override files for iCal events (committed via PR)
_groups/             # Group/meetup configurations with iCal/RSS feeds
_single_events/      # Manually submitted single events
templates/           # Jinja2 HTML templates
static/              # CSS, JavaScript, and images
```

## 📝 Adding Events

### Add a Group/Meetup

Visit `/submit-group/` or create a YAML file in `_groups/` with your group's RSS or iCal feed.

### Add a Single Event

Visit `/submit/` or create a YAML file in `_single_events/` (format: `YYYY-MM-DD-event-title.yaml`).

#### Multi-Day Events with Different Times Per Day

For multi-day events where the time varies by day, use a dictionary for the `time` field with date keys:

```yaml
title: Data Center World 2026
date: '2026-04-20'
end_date: '2026-04-23'
url: https://datacenterworld.com
location: Washington, DC
time:
  '2026-04-21': '14:00'
  '2026-04-22': '10:00'
  '2026-04-23': '10:00'
```

Each date should be in `YYYY-MM-DD` format with the time in `HH:MM` (24-hour) format. Days not specified in the dictionary will display as "All Day" events.

## 🏷️ Categories

Events can be organized by category. Categories are defined in `_categories/` as YAML files:

```yaml
name: "Python"
description: "Python programming language events"
```

### Assigning Categories

**To a group** (all events inherit these categories):
```yaml
# _groups/python-users.yaml
name: "DC Python Users"
ical: "https://example.com/calendar.ics"
categories:
  - python
```

**To a single event**:
```yaml
# _single_events/2025-03-15-pycon-dc.yaml
title: "PyCon DC"
date: "2025-03-15"
categories:
  - python
  - conferences
```

**Priority**: Event-specific categories override group categories.

### Browse by Category

Visit `/categories/{slug}/` to see all events in a category (e.g., `/categories/python/`).

## ✏️ Editing Events

Events can be edited via the web interface at `/edit/{event_id}/`. The edit button appears on event listings for logged-in users.

### How It Works

1. Click the "Edit" button on any event
2. Log in with GitHub (if not already authenticated)
3. Modify event details (title, date, time, location, categories)
4. Submit creates a pull request with your changes
5. Changes go live after PR is reviewed and merged

### How Edits Are Stored

- **Manual events** (`_single_events/`): The original YAML file is updated
- **iCal events**: An override file is created in `_event_overrides/{hash}.yaml`

Override files only store the changed fields and are merged with the original iCal data during the build process.

## 🚀 Deployment

The site is automatically deployed to AWS S3 + CloudFront on every push to the `main` branch using GitHub Actions with OIDC federation.

### Deployment Architecture

- **Infrastructure**: AWS CDK (TypeScript) in `infrastructure/` directory
- **Hosting**: S3 bucket + CloudFront CDN
- **DNS**: Route53
- **CI/CD**: GitHub Actions with OIDC (no stored AWS credentials)

### Infrastructure Setup

See [`infrastructure/README.md`](./infrastructure/README.md) for detailed instructions on:
- Deploying the CDK stack to AWS
- Configuring GitHub Actions with repository variables
- Troubleshooting deployment issues

### Deployment Workflow

When you push to `main`:

1. GitHub Actions workflow triggers automatically
2. Builds the site using Node.js and Python
3. Authenticates to AWS using OIDC federation
4. Syncs built files to S3 bucket
5. Invalidates CloudFront cache (instant deployment)
6. Site is live at https://dctech.events

**No long-lived AWS credentials are stored in GitHub.**

### Manual Deployment

To manually deploy after making infrastructure changes:

```bash
# In the infrastructure directory
cd infrastructure
npm install
npm run build
npm run cdk deploy
```

## 🧹 Event Maintenance

### Address Handling

For aggregated events, the system extracts and displays city and state information only (e.g., "Arlington, VA"). This simplifies location handling and eliminates the need for complex address normalization. The `usaddress` library is used to accurately parse various address formats and extract city/state components.

Address extraction works with:
- Full street addresses: "1630 7th St NW, Washington, DC 20001" → "Washington, DC"
- City and state: "Arlington, VA 22201" → "Arlington, VA"
- Addresses with venue names: "The White House, 1600 Pennsylvania Avenue NW, Washington, DC" → "Washington, DC"

### Automatic Pruning

A GitHub Actions workflow runs on the 1st of each month to identify and remove old events (more than 7 days past their date). The workflow creates a pull request with the proposed deletions for review before merging.

### Manual Pruning

To manually prune old events:

```bash
python prune_old_events.py           # Delete old events
python prune_old_events.py --dry-run # Preview what would be deleted
python prune_old_events.py --days 14 # Keep events for 14 days instead
```

## 🤝 Contributing

- **Add events/groups**: Use the web forms (`/submit/` or `/submit-group/`) or submit a pull request with YAML files
- **Report issues**: Open an issue on GitHub
- **Improve code**: Fork, branch, code, and submit a pull request

### Development Workflow

1. **Validate changes**: Run `make validate` to check YAML files before submitting
2. **Run tests**: Execute `python -m unittest discover -s . -p "test_*.py"` to run all unit tests
3. **Submit PR**: All pull requests trigger automated tests via GitHub Actions

Pull requests require passing tests before they can be merged to the main branch.

## 📜 License

MIT License

---

**Site**: https://dctech.events  
**Issues**: https://github.com/rosskarchner/dctech.events/issues
