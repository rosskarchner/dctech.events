# Event Tracking and RSS Feed

This document describes the event tracking system, RSS feed, and daily summary features.

## Overview

The system tracks when events are first added to the site, maintains a history in S3, and provides:
- RSS feed of recently added events
- Daily summaries posted to micro.blog
- Historical tracking of event additions

## Components

### 1. Event Tracking (`track_events.py`)

**Purpose**: Persist `upcoming.yaml` to S3 and detect newly added events.

**How it works**:
- Uploads current `upcoming.yaml` to S3 with timestamp
- Compares with previous version to identify new events
- Maintains metadata about when each event was first seen

**S3 Structure**:
```
upcoming-history/
  ├── 2026-02-01-14-30-00.yaml  # Timestamped snapshots
  ├── 2026-02-01-18-00-00.yaml
  ├── latest.yaml                # Most recent version
  └── metadata.json              # Event tracking metadata
```

**Usage**:
```bash
export S3_BUCKET=your-bucket-name
python track_events.py              # Track and upload
python track_events.py --dry-run    # Test without uploading
```

**When it runs**: 
- Automatically after each deployment (via GitHub Actions)
- Daily at 2 AM ET / 6 AM UTC

### 2. RSS Feed (`generate_rss_feed.py`)

**Purpose**: Generate RSS 2.0 feed of recently added events.

**How it works**:
- Reads event metadata from S3
- Filters to events added in last 30 days
- Generates standard RSS 2.0 XML

**Feed URL**: `https://dctech.events/events-feed.xml`

**Usage**:
```bash
export S3_BUCKET=your-bucket-name
python generate_rss_feed.py > feed.xml
python generate_rss_feed.py --days 7 --max-items 20
```

**Options**:
- `--days N`: Look back N days (default: 30)
- `--max-items N`: Max items in feed (default: 50)

### 3. Daily Summary (`post_daily_event_summary.py`)

**Purpose**: Post daily summary of new events to micro.blog.

**How it works**:
- Checks S3 metadata for events added today
- If new events found, generates a simple text post with link
- Posts to micro.blog using Micropub API (untitled post)

**Post format**: 
```
Content: "X new events added today: https://dctech.events/just-added/#M-D-YYYY"
(No title - creates an untitled post)
```

**Example**:
```
3 new events added today: https://dctech.events/just-added/#2-5-2026
```

**Usage**:
```bash
export S3_BUCKET=your-bucket-name
export MB_TOKEN=your-microblog-token
# MICROBLOG_DESTINATION is no longer needed - defaults to https://updates.dctech.events/
python post_daily_event_summary.py
python post_daily_event_summary.py --dry-run
python post_daily_event_summary.py --date 2026-02-01
```

**When it runs**: 
- Automatically daily at 11 PM UTC / 6 PM ET (via GitHub Actions)

### 4. Just-Added Page (`/just-added/`)

**Purpose**: Display the three most recent days with newly added events.

**Features**:
- Shows events grouped by the date they were added (not event date)
- Excludes days with more than 100 events (likely bulk imports)
- Each day has a date-based anchor (e.g., `#2-5-2026`)
- Links from daily summary posts point to these anchors

**URL Structure**:
- Main page: `https://dctech.events/just-added/`
- With anchor: `https://dctech.events/just-added/#2-5-2026`

**Data Source**: DynamoDB table (via `db_utils.get_recently_added()`)

## GitHub Actions Workflows

### Deploy Workflow (`.github/workflows/deploy.yml`)

**Schedules**:
- Daily at 6 AM UTC (2 AM ET) - Main rebuild
- Daily at 10:30 PM UTC - Pre-summary rebuild to update just-added page

**Critical Step Order**:

The workflow must track events **before** generating the static site to ensure consistent counts:

```yaml
- name: Configure AWS credentials via OIDC
  # ... AWS setup

- name: Track events and persist to S3
  run: python track_events.py

- name: Generate static site
  run: make all
```

**Why this order matters**:
1. `make all` includes `freeze.py` which generates the static `/just-added/` page
2. The frozen page reads S3 metadata to display event counts
3. `track_events.py` detects new events and updates the S3 metadata
4. If tracking runs after freezing, the static page will show stale counts while `post_daily_event_summary.py` reports the updated count, causing a discrepancy

### Daily Summary Workflow (`.github/workflows/post-daily-event-summary.yml`)

Runs daily at 11 PM UTC (6 PM ET) to post summaries to micro.blog.

**Manual triggers**: Can run manually with optional parameters:
- `dry_run`: Test without posting
- `date`: Check specific date (YYYY-MM-DD)

## Environment Variables

Required for all scripts:
- `S3_BUCKET`: S3 bucket name for event history
- `AWS_REGION`: AWS region (default: us-east-1)

Required for daily summary:
- `MB_TOKEN`: Micro.blog app token
- ~~`MICROBLOG_DESTINATION`~~: **No longer used** - defaults to `https://updates.dctech.events/` (hardcoded in script)

## Event Identification

Events are uniquely identified by:
1. **iCal events**: `guid` field (MD5 hash of date/time/title/url)
2. **Manual events**: `id` field (filename-based)
3. **Fallback**: Combination of date, time, and title

## Testing

Run tests:
```bash
python3 -m pytest test_event_tracking.py -v
```

Tests cover:
- Event key generation
- New event detection
- Metadata updates
- RSS feed generation
- Daily summary posting
- HTML generation

## AWS Permissions

The GitHub Actions role needs these S3 permissions (already included in CDK stack):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::bucket-name/*",
        "arn:aws:s3:::bucket-name"
      ]
    }
  ]
}
```

**Note**: The CDK stack (`infrastructure/lib/dctech-events-stack.ts`) has been updated to include `s3:GetObject` permission for the GitHub Actions role. If the infrastructure was deployed before this change, you'll need to redeploy it:

```bash
cd infrastructure
npm run cdk deploy
```

## Troubleshooting

**RSS feed shows "not yet available"**:
- S3_BUCKET environment variable not set
- No metadata.json exists in S3 yet
- AWS credentials not configured

**Daily summary not posting**:
- Check MB_TOKEN is set correctly
- Verify events were actually added that day
- Check GitHub Actions logs for errors

**No new events detected**:
- Ensure upcoming.yaml changed between runs
- Check event keys are consistent (guid/id fields)
- Verify track_events.py ran successfully

## Future Enhancements

Potential improvements:
- Weekly digest in addition to daily summaries
- Email notifications for new events
- RSS feed filtering by category
- Historical analytics dashboard
