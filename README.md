# DC Tech Events

A static site generator for aggregating and displaying tech events in the DC area.

## Project Structure

- `_groups/`: YAML files describing each tech group
- `_single_events/`: YAML files for events that don't come from groups
- `_data/`: Generated YAML files containing event data
- `_cache/`: Cache for downloaded iCal files
- `app.py`: Flask application for rendering the site
- `build/`: Generated static site

## Local Development

### Prerequisites

- Python 3.8+
- pip

### Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run the aggregator to fetch events:

```bash
python aggregator.py
```

3. Run the Flask app locally:

```bash
python app.py
```

4. Visit http://localhost:5000 in your browser

### Building the Static Site

To build the complete static site:

```bash
make all
```

This will:
1. Fetch iCal files from group sources
2. Generate YAML files with event data
3. Build the static site using Flask-Frozen

The generated site will be in the `build/` directory.

## Adding Content

### Adding a Group

Create a new YAML file in the `_groups/` directory with the following format:

```yaml
name: Group Name
website: https://example.com
ical: https://example.com/events.ics
fallback_url: https://example.com/events  # Optional
active: true  # Optional, defaults to true
```

### Adding a Single Event

Create a new YAML file in the `_single_events/` directory with the following format:

```yaml
title: Event Title
date: 2023-12-15  # YYYY-MM-DD
time: 18:00  # 24-hour format
end_date: 2023-12-15  # Optional
end_time: 20:00  # Optional
url: https://example.com/event
description: Event description
location: Event location
group: Organizing Group
```

## Deployment

The site is automatically deployed to GitHub Pages when changes are pushed to the main branch.

## Makefile Commands

- `make all`: Run the complete build process
- `make fetch`: Fetch iCal files (Phase 1)
- `make generate`: Generate YAML files (Phase 2)
- `make freeze`: Generate the static site
- `make clean`: Clean build artifacts