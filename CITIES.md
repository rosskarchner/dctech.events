# Adding a New City to LocalTech.Events

This guide explains how to add a new city to the LocalTech.Events platform.

## Overview

LocalTech.Events is a multi-city platform for technology events. Each city has its own subdomain (e.g., `dc.localtech.events`, `sf.localtech.events`) and maintains its own data independently.

## Prerequisites

- Fork and clone this repository
- Basic familiarity with YAML files
- Python 3.10+ installed (for local testing)
- Node.js 20+ installed (for local testing)

## Step-by-Step Guide

### 1. Create City Directory Structure

Create a new directory under `cities/` with your city's slug (lowercase, alphanumeric, hyphens allowed):

```bash
mkdir -p cities/{city-slug}/_groups
mkdir -p cities/{city-slug}/_single_events
mkdir -p cities/{city-slug}/_data
```

Example for Austin, TX:
```bash
mkdir -p cities/austin/_groups
mkdir -p cities/austin/_single_events
mkdir -p cities/austin/_data
```

### 2. Create Sponsors Configuration

Create a `sponsors.yaml` file in your city directory:

```bash
cat > cities/{city-slug}/sponsors.yaml << EOF
# GitHub Sponsors for {City Name} Tech Events
# Add GitHub usernames of sponsors here (one per line)
# These will be verified against GitHub Sponsors API during build
sponsors: []
EOF
```

### 3. Add City Configuration

Edit `config.yaml` and add your city to the `cities` array:

```yaml
cities:
  - slug: dc
    name: "Washington DC"
    tagline: Technology conferences and meetups in and around Washington, DC
    timezone: "US/Eastern"
    location: "Washington, DC"
    max_distance_miles: 50
    base_url: https://dc.localtech.events
    add_events_link: https://add.dctech.events/dctech
    newsletter_signup_link: https://newsletter.dctech.events/

  # Add your city here
  - slug: austin  # URL-friendly slug (used in subdomain)
    name: "Austin"  # Display name
    tagline: Technology conferences and meetups in and around Austin, TX
    timezone: "US/Central"  # IANA timezone identifier
    location: "Austin, TX"  # Used for geocoding
    max_distance_miles: 50  # Search radius for nearby events
    base_url: https://austin.localtech.events
    add_events_link: https://austin.localtech.events/submit/
    newsletter_signup_link: ""  # Optional
```

### 4. Add Groups (Meetups/Organizations)

Create YAML files in `cities/{city-slug}/_groups/` for recurring event groups:

**Filename format:** `{group-name}.yaml` (lowercase, use hyphens)

**Example:** `cities/austin/_groups/austin-python-meetup.yaml`

```yaml
active: true
name: Austin Python Meetup
rss: https://www.meetup.com/austin-python-meetup/events/rss/
submitted_by: your-github-username
submitter_link: 'https://github.com/your-username'
website: https://www.meetup.com/austin-python-meetup/
```

**Field descriptions:**
- `active`: Set to `true` to include this group
- `name`: Display name of the group
- `rss`: RSS/iCal feed URL for events (must be publicly accessible)
- `submitted_by`: Your GitHub username
- `submitter_link`: Link to your GitHub profile
- `website`: Group's primary website

**Supported RSS/iCal sources:**
- Meetup.com: `https://www.meetup.com/{group-name}/events/rss/`
- Eventbrite: `https://www.eventbrite.com/rss/organizer_list_events/{organizer-id}`
- Luma: `https://lu.ma/api/calendar/ics/get-ics-url?entity={entity-id}`
- Any public iCal (.ics) URL

### 5. Add Single Events (Optional)

For one-time or special events, create YAML files in `cities/{city-slug}/_single_events/`:

**Filename format:** `{YYYY-MM-DD}-{event-title}.yaml`

**Example:** `cities/austin/_single_events/2025-12-15-austin-tech-summit.yaml`

```yaml
date: '2025-12-15'
location: Austin Convention Center, 500 E Cesar Chavez St, Austin, TX 78701
submitted_by: your-github-username
submitter_link: 'https://github.com/your-username'
time: '09:00'
title: 'Austin Tech Summit 2025'
url: https://example.com/austin-tech-summit
```

**Field descriptions:**
- `date`: Event date in YYYY-MM-DD format (quoted)
- `location`: Full address (used for geocoding and display)
- `submitted_by`: Your GitHub username
- `submitter_link`: Link to your GitHub profile
- `time`: Start time in HH:MM format (24-hour, quoted)
- `title`: Event title
- `url`: Event website or registration page

### 6. Test Locally (Optional)

```bash
# Install dependencies
pip install -r requirements.txt
npm install

# Build your city
CITY=austin make all

# Run local dev server
python app.py --city austin
```

Visit `http://localhost:5000` to preview your city site.

### 7. Submit Pull Request

1. Commit your changes:
   ```bash
   git add cities/austin/
   git add config.yaml
   git commit -m "Add Austin, TX city"
   ```

2. Push to your fork:
   ```bash
   git push origin main
   ```

3. Create a pull request at https://github.com/rosskarchner/dctech.events/pulls

## City Configuration Reference

### Timezone Identifiers

Use IANA timezone identifiers. Common US timezones:
- `US/Eastern` - New York, Washington DC, Atlanta
- `US/Central` - Chicago, Austin, Dallas
- `US/Mountain` - Denver, Phoenix
- `US/Pacific` - San Francisco, Seattle, Los Angeles
- `US/Alaska` - Anchorage
- `US/Hawaii` - Honolulu

Full list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

### Location Format

Use full city and state format for best geocoding results:
- ✅ "San Francisco, CA"
- ✅ "Austin, TX"
- ✅ "Seattle, WA"
- ❌ "SF" (too ambiguous)
- ❌ "Austin" (could be confused with other cities)

### Max Distance

The `max_distance_miles` setting controls the search radius for nearby events:
- **50 miles** - Good for most cities (default)
- **100 miles** - Large metro areas or sparse regions
- **25 miles** - Dense urban areas

## Content Guidelines

### What to Include

✅ Technology-focused meetups and conferences
✅ Software development communities
✅ Data science and AI groups
✅ DevOps and infrastructure meetups
✅ Design and UX communities
✅ Open source projects
✅ Hackathons and coding events

### What to Exclude

❌ Non-tech events
❌ Private/invite-only events
❌ Events requiring paid registration (unless clearly marked)
❌ Recruiting events (unless educational content)
❌ Spam or promotional content

## Moderation

Each city's content is moderated by the community. If you notice:
- Inactive groups (no events in 6+ months)
- Broken RSS feeds
- Inappropriate content
- Spam

Please open an issue or submit a PR to update the data.

## RSS Feed Troubleshooting

### Testing RSS Feeds

```bash
# Test if RSS feed is accessible
curl -I "https://www.meetup.com/group-name/events/rss/"

# View RSS feed contents
curl "https://www.meetup.com/group-name/events/rss/"
```

### Common Issues

1. **403 Forbidden**: Feed requires authentication or has rate limiting
2. **404 Not Found**: Group doesn't exist or feed URL is incorrect
3. **Empty feed**: Group has no upcoming events (this is okay)
4. **Invalid XML**: Feed format is broken (contact organizer)

### Meetup.com Specific

Meetup.com RSS feeds are publicly accessible at:
```
https://www.meetup.com/{urlname}/events/rss/
```

To find the `urlname`:
1. Visit the group's page
2. Look at the URL: `https://www.meetup.com/{urlname}/`
3. Use that `urlname` in the RSS URL

## FAQ

### Q: Can I add events from neighboring cities?

Yes! If events are within your city's `max_distance_miles`, they'll appear automatically. The platform uses geocoding to determine distance.

### Q: How often are events updated?

Event feeds are refreshed every 4 hours during the build process. The site is rebuilt daily via GitHub Actions.

### Q: Can I add events without an RSS feed?

Yes! Use the `_single_events/` directory for one-time events. However, recurring events should have an RSS/iCal feed when possible.

### Q: How do I become a city maintainer?

Open an issue expressing interest! City maintainers help review PRs, keep data up-to-date, and promote the site locally.

### Q: Can I add sponsor logos?

Yes! Sponsors are verified via GitHub Sponsors. Add GitHub usernames to `cities/{city-slug}/sponsors.yaml`. Only verified sponsors will be displayed.

## Getting Help

- **Questions**: Open an issue with the `question` label
- **Bug reports**: Open an issue with the `bug` label
- **Feature requests**: Open an issue with the `enhancement` label
- **Chat**: Join discussions in GitHub Discussions

## Examples

See existing cities for reference:
- Washington DC: `cities/dc/`
- San Francisco: `cities/sf/` (test data)

## Architecture

For technical details about how the multi-city platform works, see:
- `NEXT_STEPS.md` - Original implementation plan
- `IMPLEMENTATION_STATUS.md` - Current status
- `INFRASTRUCTURE.md` - AWS infrastructure details
