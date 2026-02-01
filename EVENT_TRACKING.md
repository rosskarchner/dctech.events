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
- If new events found, generates HTML summary
- Posts to micro.blog using Micropub API

**Post format**: 
```
Title: "X new events added on May 3rd 2026"
Content: HTML list of event titles and dates with links
```

**Usage**:
```bash
export S3_BUCKET=your-bucket-name
export MB_TOKEN=your-microblog-token
export MICROBLOG_DESTINATION=https://updates.dctech.events/
python post_daily_event_summary.py
python post_daily_event_summary.py --dry-run
python post_daily_event_summary.py --date 2026-02-01
```

**When it runs**: 
- Automatically daily at 1 PM ET / 6 PM UTC (via GitHub Actions)

## GitHub Actions Workflows

### Deploy Workflow (`.github/workflows/deploy.yml`)

Added step after deployment:
```yaml
- name: Track events and persist to S3
  run: python track_events.py
```

### Daily Summary Workflow (`.github/workflows/post-daily-event-summary.yml`)

Runs daily at 6 PM UTC to post summaries to micro.blog.

**Manual triggers**: Can run manually with optional parameters:
- `dry_run`: Test without posting
- `date`: Check specific date (YYYY-MM-DD)

## Environment Variables

Required for all scripts:
- `S3_BUCKET`: S3 bucket name for event history
- `AWS_REGION`: AWS region (default: us-east-1)

Required for daily summary:
- `MB_TOKEN`: Micro.blog app token
- `MICROBLOG_DESTINATION`: (Optional) Custom domain for multi-blog accounts

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

The GitHub Actions role needs these S3 permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
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
