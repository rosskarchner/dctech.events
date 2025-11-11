# Adding Events to DC Tech Events

This guide explains how to add events to the DC Tech Events website, both with automation scripts and manually.

## Table of Contents

- [Quick Start](#quick-start)
- [Adding Events with Scripts](#adding-events-with-scripts)
- [Adding Events Manually](#adding-events-manually)
- [Adding Tech Groups](#adding-tech-groups)
- [Event Data Format](#event-data-format)
- [Validation and Testing](#validation-and-testing)

## Quick Start

**For single events from supported platforms:**
```bash
# Luma events
python add-luma.py https://lu.ma/event-slug

# Eventbrite events
python add-eventbrite.py https://www.eventbrite.com/e/event-id
```

**For recurring events or new tech groups:**
```bash
# Add a Meetup group
python add_meetup.py

# Add any other group manually
python add_group.py
```

## Adding Events with Scripts

The repository includes automated scripts for extracting event data from popular platforms.

### Using add-luma.py

The `add-luma.py` script extracts event details from lu.ma and luma.com URLs.

**Usage:**
```bash
python add-luma.py https://lu.ma/your-event-slug
```

**What it does:**
1. Fetches the event page and extracts JSON-LD structured data
2. Parses start/end dates and times (ISO 8601 format)
3. Extracts venue name and address
4. Determines if the event is free or paid
5. Creates a YAML file in `_single_events/` directory
6. Falls back to manual entry if structured data is unavailable

**Example output file:** `_single_events/2025-06-06-ai-collective-dc-|-launch-party-🚀.yaml`

### Using add-eventbrite.py

Similar to the Luma script, but for Eventbrite events.

**Usage:**
```bash
python add-eventbrite.py https://www.eventbrite.com/e/event-id
```

**What it does:**
- Extracts JSON-LD Event data from Eventbrite pages
- Parses event metadata (title, date, time, location, pricing)
- Creates YAML file in `_single_events/`

## Adding Events Manually

If you need to add an event that isn't from a supported platform, or if the scripts fail, you can create event files manually.

### Creating a Single Event File

1. **Navigate to the `_single_events/` directory**

2. **Create a new YAML file** with the naming convention:
   ```
   YYYY-MM-DD-{slugified-title}.yaml
   ```
   Example: `2025-06-15-dc-tech-meetup.yaml`

3. **Add event data** using this template:

```yaml
title: "Your Event Title"
date: '2025-06-15'
time: '18:30'
end_date: '2025-06-15'  # Optional, for multi-day events
end_time: '20:00'        # Optional
url: https://example.com/event
location: 'Venue Name, 123 Street Name, City, State'
cost: null               # Use null for free events, or a string like "$25"
submitted_by: your-name
submitter_link: https://example.com/your-profile
```

### Field Requirements

**Required fields:**
- `title`: Event name (string)
- `date`: Event date in 'YYYY-MM-DD' format (quoted string)
- `time`: Start time in 'HH:MM' format, 24-hour (quoted string)
- `url`: Link to event page (string)

**Optional fields:**
- `end_date`: End date for multi-day events (quoted string)
- `end_time`: End time in 'HH:MM' format (quoted string)
- `location`: Full address as "Venue, Street, City, State" (string)
- `cost`: Price information or null for free events
- `submitted_by`: Your name or identifier (string)
- `submitter_link`: Link to your profile or website (string)

### Location Format

The location field should follow this pattern for best results:
```
"Venue Name, Street Address, City, State"
```

Examples:
- `"Great Frogs Winery, Alexandria, VA"`
- `"WeWork Dupont Circle, 1875 Connecticut Ave NW, Washington, DC"`
- `"Online"` (for virtual events)

The system will parse this to extract city and state for filtering.

## Adding Tech Groups

Tech groups provide recurring events through iCal or RSS feeds. This is the preferred method for organizations that regularly host events.

### Using add_meetup.py (Interactive)

For Meetup.com groups:

```bash
python add_meetup.py
```

The script will:
1. Prompt for the Meetup group URL
2. Extract the group name from the page
3. Create a YAML file in `_groups/` with the RSS feed URL
4. Ask if you want to add more groups

### Using add_group.py (Manual Entry)

For other platforms (Luma, Eventbrite, or any iCal source):

```bash
python add_group.py
```

This interactive script will guide you through creating a group configuration.

### Manual Group File Creation

Create a file in `_groups/` directory:

**For iCal-based groups (Luma calendars, etc.):**

```yaml
name: Group Name
website: https://group-website.com
ical: https://api.lu.ma/ics/get?entity=calendar&id=cal-XXXXX
fallback_url: https://lu.ma/group-name
active: true
```

**For RSS-based groups (Meetup.com):**

```yaml
name: Group Name
website: https://www.meetup.com/group-name/
rss: https://www.meetup.com/group-name/events/rss/
active: true
```

**Field descriptions:**
- `name`: Display name of the tech group
- `website`: Group's homepage or main URL
- `ical`: iCal feed URL (if available)
- `rss`: RSS feed URL (primarily for Meetup)
- `fallback_url`: Backup URL if calendar fetch fails
- `active`: Set to `true` to include in event fetching

## Event Data Format

### File Naming Convention

**Single events:**
```
_single_events/YYYY-MM-DD-{slug}.yaml
```

**Groups:**
```
_groups/{group-slug}.yaml
```

Slugs should be lowercase, with hyphens replacing spaces and special characters.

### Time Format

- **Dates**: Always use 'YYYY-MM-DD' format, quoted as a string
- **Times**: Always use 'HH:MM' in 24-hour format, quoted as a string
- **Timezone**: All times are assumed to be US/Eastern (the build process handles timezone conversion)

### Examples

**Multi-day conference:**
```yaml
title: "DC Tech Summit 2025"
date: '2025-09-10'
time: '09:00'
end_date: '2025-09-12'
end_time: '17:00'
url: https://dctechsummit.example.com
location: 'Walter E. Washington Convention Center, 801 Mt Vernon Pl NW, Washington, DC'
cost: "$299"
submitted_by: conference-organizers
submitter_link: https://dctechsummit.example.com/about
```

**Free evening meetup:**
```yaml
title: "Python User Group Monthly Meeting"
date: '2025-06-20'
time: '18:30'
end_time: '20:30'
url: https://meetup.com/example
location: 'TechSpace, Arlington, VA'
cost: null
submitted_by: community-member
submitter_link: ''
```

## Validation and Testing

### Local Testing

After adding events, test the build process:

```bash
# Clean previous builds
make clean

# Run full build pipeline
make

# Or step by step:
make refresh-calendars      # Fetch calendar data
make generate-month-data    # Process events
make freeze                 # Generate static site

# Run local development server
flask run --debug
```

Visit http://localhost:5000 to see your changes.

### Validation Checks

The system performs several validations during the build:

1. **YAML syntax**: Files must be valid YAML
2. **Required fields**: title, date, time, and url must be present
3. **Date format**: Dates must be in YYYY-MM-DD format
4. **Location filtering**: Events more than 50 miles from DC center are filtered out
5. **Duplicate detection**: Events with matching title + date + time are deduplicated

### Common Issues

**Event not appearing:**
- Check that the date is in the future
- Verify the location is within 50 miles of DC
- Ensure all required fields are present
- Check YAML syntax is valid

**Duplicate events:**
- The system automatically deduplicates based on title + date + time
- If you see duplicates, check for slight variations in these fields

**Location not recognized:**
- Use the format: "Venue, Street, City, State"
- Include at least city and state abbreviation
- For online events, use "Online" as the location

## Contributing via Web Interface

The website includes submission forms at:
- `/submit/` - For single events
- `/submit-group/` - For new tech groups

These forms use GitHub OAuth to create pull requests automatically. The workflow:
1. Fill out the form
2. Authenticate with GitHub
3. System creates a PR with your event/group YAML file
4. Maintainers review and merge
5. GitHub Actions rebuilds and deploys the site

## Build Pipeline

Understanding the build process helps with troubleshooting:

```
_groups/*.yaml + _single_events/*.yaml
         ↓
   refresh_calendars.py (fetches iCal/RSS feeds)
         ↓
   generate_month_data.py (deduplicates, normalizes)
         ↓
   _data/upcoming.yaml (consolidated event list)
         ↓
   app.py (Flask renders templates)
         ↓
   freeze.py (generates static HTML)
         ↓
   build/ directory (deployable site)
```

## Need Help?

- Check existing event files in `_single_events/` for examples
- Review group configurations in `_groups/` for reference
- Run `make validate` to check for common issues
- The build process outputs helpful error messages

## Summary

- **Quick events**: Use `add-luma.py` or `add-eventbrite.py` scripts
- **Manual events**: Create YAML files in `_single_events/`
- **Recurring events**: Add groups to `_groups/` directory
- **Test locally**: Run `make` and `flask run --debug`
- **Web submission**: Use the forms at `/submit/` and `/submit-group/`
