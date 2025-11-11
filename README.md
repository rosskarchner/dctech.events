# LocalTech Events (formerly DC Tech Events)

A multi-city platform for aggregating and displaying technology events. Originally created for Washington DC, now expanding to support multiple cities across the US.

## 🌆 Multi-City Platform

LocalTech Events hosts separate event calendars for different cities:

- **Washington DC**: `dc.localtech.events` (also `dctech.events` via GitHub Pages)
- **Baltimore**: `baltimore.localtech.events`
- **Philadelphia**: `philadelphia.localtech.events`
- **Pittsburgh**: `pittsburgh.localtech.events`
- **Richmond**: `richmond.localtech.events`

Each city maintains its own independent data and event sources.

## 📁 Project Structure

```
dctech.events/
├── cities/                  # City-specific data
│   ├── dc/                  # Washington DC
│   │   ├── _groups/         # Tech groups and meetups (110+ files)
│   │   ├── _single_events/  # One-time events
│   │   ├── _data/           # Generated event data
│   │   └── sponsors.yaml    # GitHub sponsors configuration
│   ├── baltimore/           # Baltimore, MD
│   ├── philadelphia/        # Philadelphia, PA
│   ├── pittsburgh/          # Pittsburgh, PA
│   └── richmond/            # Richmond, VA
├── infrastructure/          # AWS CDK infrastructure code
│   ├── bin/app.ts
│   ├── lib/localtech-stack.ts
│   └── ...
├── templates/               # Jinja2 templates
│   ├── city_index.html      # Homepage (city directory)
│   ├── homepage.html        # City-specific homepage
│   └── ...
├── oauth-endpoint/          # GitHub OAuth Lambda function
├── config.yaml              # Multi-city configuration
├── app.py                   # Flask application
├── freeze.py                # Static site generator
├── refresh_calendars.py     # Event feed fetcher
└── generate_month_data.py   # Event data aggregator
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

2. **Build a city** (DC by default):

```bash
make all
```

Or build a specific city:

```bash
CITY=baltimore make all
```

3. **Run the dev server**:

```bash
# Run DC site
python app.py

# Run a specific city
python app.py --city baltimore

# Run the multi-city homepage
python app.py --homepage
```

4. **Visit** `http://localhost:5000` in your browser

## 🏗️ Building Sites

### Build DC (Default)

```bash
make all
```

This builds the DC site to `build/` directory.

### Build Any City

```bash
CITY=philadelphia make all
```

### Build Homepage

```bash
make homepage
```

This creates the localtech.events homepage showing all cities.

### Build All Cities

```bash
for city in dc baltimore philadelphia pittsburgh richmond; do
  CITY=$city make all
done
```

## 📝 Adding Content

### Adding a Group (Tech Meetup/Organization)

**Option 1: Web Form** (Recommended)

Visit `/submit-group/` on any city site to submit via GitHub OAuth.

**Option 2: Manual PR**

Create a YAML file in `cities/{city-slug}/_groups/`:

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

Visit `/submit/` on any city site to submit via GitHub OAuth.

**Option 2: Manual PR**

Create a YAML file in `cities/{city-slug}/_single_events/`:

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

### Adding a New City

See **[CITIES.md](CITIES.md)** for detailed instructions on adding a new city.

Quick summary:
1. Create `cities/{city-slug}/` directory structure
2. Add city configuration to `config.yaml`
3. Add groups and events
4. Submit pull request

## 🏭 Architecture

### Multi-City Design

Each city operates independently:

- **Data**: Stored in `cities/{city-slug}/`
- **Build**: Each city builds separately with `CITY={slug} make all`
- **Deploy**: All cities deploy to S3 with subdomain routing

### Deployment Targets

**DC Site** → GitHub Pages
- Domain: `dctech.events`
- Workflow: `.github/workflows/deploy.yml`
- Trigger: Push to main, daily cron

**All Cities** → AWS S3 + CloudFront
- Domain: `localtech.events` and `*.localtech.events`
- Workflow: `.github/workflows/deploy-localtech.yml`
- Trigger: Push to main, daily cron

### Routing

CloudFront Function routes requests:

```
localtech.events            → /index.html (homepage)
dc.localtech.events         → /dc/index.html
baltimore.localtech.events  → /baltimore/index.html
```

See **[INFRASTRUCTURE.md](INFRASTRUCTURE.md)** for AWS setup details.

## 🛠️ Development

### Make Targets

```bash
make all              # Build DC site (default)
make homepage         # Build localtech.events homepage
make clean            # Remove build artifacts
make validate         # Validate all YAML files
make js-build         # Build JavaScript bundles
```

### Environment Variables

- `GITHUB_CLIENT_ID`: OAuth client ID for event submission
- `GITHUB_SPONSORS_TOKEN`: GitHub API token for sponsor verification

Set these in `.env` or export them:

```bash
export GITHUB_CLIENT_ID=your_client_id
export GITHUB_SPONSORS_TOKEN=your_token
```

### City-Specific Commands

```bash
# Refresh event feeds for Baltimore
CITY=baltimore python refresh_calendars.py --city baltimore

# Generate event data for Philadelphia
CITY=philadelphia python generate_month_data.py --city philadelphia

# Build static site for Pittsburgh
CITY=pittsburgh python freeze.py --city pittsburgh
```

## 🚢 Deployment

### Automated Deployments

Three GitHub Actions workflows handle deployments:

1. **`deploy.yml`** - DC site to GitHub Pages
   - Builds `cities/dc/` → `dctech.events`
   - Runs daily at 2 AM Eastern

2. **`deploy-localtech.yml`** - All cities to AWS
   - Builds all cities → `localtech.events`
   - Requires AWS credentials in GitHub Secrets

3. **`deploy-infrastructure.yml`** - AWS infrastructure
   - Deploys CDK stack when `infrastructure/**` changes
   - Creates S3, CloudFront, Route53 resources

### Required GitHub Secrets

For AWS deployment:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `CLOUDFRONT_DISTRIBUTION_ID` (after first deployment)
- `S3_BUCKET_NAME` (after first deployment)

### Manual Deployment

**Deploy infrastructure**:
```bash
cd infrastructure
npm install
npx cdk deploy
```

**Build and upload content**:
```bash
# Build all cities
make homepage
for city in dc baltimore philadelphia pittsburgh richmond; do
  CITY=$city make all
  mkdir -p build-all/$city
  mv build/* build-all/$city/
done

# Upload to S3
aws s3 sync build-all/ s3://localtech-events-hosting/ --delete

# Invalidate CloudFront
aws cloudfront create-invalidation \
  --distribution-id YOUR_DISTRIBUTION_ID \
  --paths "/*"
```

## 📚 Documentation

- **[CITIES.md](CITIES.md)** - Guide for adding new cities
- **[INFRASTRUCTURE.md](INFRASTRUCTURE.md)** - AWS infrastructure setup
- **[NEXT_STEPS.md](NEXT_STEPS.md)** - Original multi-city implementation plan
- **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)** - Current implementation status
- **[oauth-endpoint/README.md](oauth-endpoint/README.md)** - OAuth endpoint documentation

## 🤝 Contributing

We welcome contributions! Here's how:

### Add Events/Groups
1. Use the web forms (`/submit/` or `/submit-group/`)
2. Or create a pull request with YAML files

### Add a City
1. Read [CITIES.md](CITIES.md)
2. Create city directory and configuration
3. Submit pull request

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
# Test DC build
make clean all

# Test another city
CITY=baltimore make clean all

# Test homepage
make homepage
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
- Run `python refresh_calendars.py --city {city}`
- Verify feeds are publicly accessible

### City Not Found Error

```bash
Error: City 'xyz' not found in config.yaml
```

Solution: Add city to `config.yaml` cities array

### Template Rendering Errors

Check that required variables are set:
- City configuration exists in `config.yaml`
- `_data/upcoming.yaml` file exists (generated by `make all`)

## 📊 Data Flow

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

## 🌐 URLs

### Production
- DC (GitHub Pages): https://dctech.events
- Homepage (AWS): https://localtech.events
- DC (AWS): https://dc.localtech.events
- Baltimore: https://baltimore.localtech.events
- Philadelphia: https://philadelphia.localtech.events
- Pittsburgh: https://pittsburgh.localtech.events
- Richmond: https://richmond.localtech.events

### Development
- Local: http://localhost:5000

## 📜 License

MIT License - See LICENSE file for details.

## 🙏 Acknowledgments

- Original DC Tech Events community
- All contributors and event organizers
- Open source projects used: Flask, Python, AWS CDK

## 📧 Contact

- GitHub Issues: https://github.com/rosskarchner/dctech.events/issues
- GitHub Discussions: For questions and community chat

---

**Note**: This project maintains backward compatibility. The original `dctech.events` continues to work unchanged, hosted on GitHub Pages. The new multi-city platform (`localtech.events`) runs in parallel on AWS infrastructure.
