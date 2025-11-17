# DC Tech Events

A platform for aggregating and displaying technology conferences and meetups in and around Washington, DC.

## 📁 Project Structure

```
dctech.events/
├── _groups/                 # Tech groups and meetups (110+ YAML files)
├── _single_events/          # One-time events
├── _data/                   # Generated event data (created during build)
├── templates/               # Jinja2 templates
├── oauth-endpoint/          # GitHub OAuth Lambda function
├── config.yaml              # Site configuration
├── app.py                   # Flask application
├── freeze.py                # Static site generator
├── refresh_calendars.py     # Event feed fetcher
├── generate_month_data.py   # Event data aggregator
└── sponsors.yaml            # GitHub sponsors configuration
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js 20+
- pip and npm

### Local Development

1. **Install dependencies**:

```bash
pip install -r requirements.txt
npm install
```

2. **Build the site**:

```bash
make all
```

3. **Run the dev server**:

```bash
python app.py
```

4. **Visit** `http://localhost:5000` in your browser

## 🏗️ Building the Site

```bash
make all           # Build everything (fetch feeds, generate data, create static site)
make clean         # Remove build artifacts
make validate      # Validate all YAML files
make js-build      # Build JavaScript bundles only
```

The build process:
1. Fetches event feeds from groups (`refresh_calendars.py`)
2. Aggregates and processes event data (`generate_month_data.py`)
3. Generates static HTML site (`freeze.py`)

Output directory: `build/`

## 📝 Adding Content

### Adding a Group (Tech Meetup/Organization)

**Option 1: Web Form** (Recommended)

Visit `/submit-group/` to submit via GitHub OAuth.

**Option 2: Manual PR**

Create a YAML file in `_groups/`:

```yaml
active: true
name: Group Name
rss: https://www.meetup.com/group-name/events/rss/
submitted_by: your-github-username
submitter_link: 'https://github.com/your-username'
website: https://www.meetup.com/group-name/
```

Supported feed formats:
- Meetup.com RSS feeds
- iCal (.ics) URLs
- RSS feeds with JSON-LD events

### Adding a Single Event

**Option 1: Web Form** (Recommended)

Visit `/submit/` to submit via GitHub OAuth.

**Option 2: Manual PR**

Create a YAML file in `_single_events/`:

**Filename**: `YYYY-MM-DD-event-title.yaml`

```yaml
date: '2025-12-15'
location: Full address with city and state
submitted_by: your-github-username
submitter_link: 'https://github.com/your-username'
time: '19:00'
title: 'Event Title'
url: https://example.com/event
```

## 🚢 Deployment

### Automated Deployment

The site automatically deploys to GitHub Pages via `.github/workflows/deploy.yml`:
- **Trigger**: Push to main branch, or daily at 2 AM Eastern
- **Domain**: `dctech.events`
- **Build**: Fetches latest event data and generates static site

### Environment Variables

- `GITHUB_CLIENT_ID`: OAuth client ID for event submission
- `GITHUB_SPONSORS_TOKEN`: GitHub API token for sponsor verification

Set these as GitHub Repository Variables/Secrets.

## 🛠️ Development

### Make Targets

```bash
make all                # Full build (refresh feeds + generate data + freeze)
make refresh-calendars  # Fetch event feeds only
make generate-month-data # Process events only
make freeze             # Generate static site only
make clean              # Remove build artifacts
make validate           # Validate YAML files
make js-build           # Build JavaScript bundles
```

### Data Flow

```
1. Groups YAML files (_groups/*.yaml)
   ↓
2. refresh_calendars.py fetches RSS/iCal feeds
   ↓
3. Events cached in _cache/
   ↓
4. generate_month_data.py aggregates events
   ↓
5. Upcoming events in _data/upcoming.yaml
   ↓
6. freeze.py generates static HTML
   ↓
7. Static site in build/
```

### Cache Management

Event feeds are cached in `_cache/` to avoid rate limiting:
- **iCal feeds**: Cached for 4 hours
- **RSS feeds**: Cached for 4 hours
- Uses HTTP conditional requests (ETag, Last-Modified)

## 🤝 Contributing

We welcome contributions!

### Add Events/Groups
1. Use the web forms (`/submit/` or `/submit-group/`)
2. Or create a pull request with YAML files

### Improve Code
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit pull request

### Report Issues
Open an issue on GitHub with:
- Description of the problem
- Steps to reproduce
- Expected vs actual behavior

## 🧪 Testing

### Validate YAML Files

```bash
make validate
```

This checks all group and event YAML files for errors.

### Test Local Build

```bash
make clean all
```

## 🐛 Troubleshooting

### Build Errors

**Missing dependencies**:
```bash
pip install -r requirements.txt
npm install
```

**Empty events file**:
- Check that groups have valid RSS/iCal feeds
- Run `python refresh_calendars.py`
- Verify feeds are publicly accessible

### Template Rendering Errors

Check that required files exist:
- `config.yaml` has valid configuration
- `_data/upcoming.yaml` exists (generated by `make all`)

## 🌐 URLs

### Production
- Main site: https://dctech.events

### Development
- Local: http://localhost:5000

## 📚 Additional Documentation

- **[ADD_EVENTS.md](ADD_EVENTS.md)** - Detailed guide for adding events
- **[HEADER_IMAGES.md](HEADER_IMAGES.md)** - Responsive header image specifications and sizes
- **[OAUTH_SETUP.md](OAUTH_SETUP.md)** - OAuth endpoint setup
- **[PR_VALIDATION.md](PR_VALIDATION.md)** - Pull request validation system
- **[ADDRESS_NORMALIZATION.md](ADDRESS_NORMALIZATION.md)** - Address formatting

## 📜 License

MIT License - See LICENSE file for details.

## 🙏 Acknowledgments

- DC Tech Events community
- All contributors and event organizers
- Open source projects: Flask, Python, GitHub Pages

## 📧 Contact

- GitHub Issues: https://github.com/rosskarchner/dctech.events/issues
- GitHub Discussions: For questions and community chat
