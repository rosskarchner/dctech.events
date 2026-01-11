# Single Events Support

Single events (manually submitted events stored as YAML files in `_single_events/`) are fully supported in the serverless architecture.

## How It Works

### 1. Event Storage

Single event YAML files are stored in the `_single_events/` directory:

```
_single_events/
├── 2026-01-16-focus-flow-coworking-session-refresh-dc.yaml
├── 2026-01-24-districtcon-year-1.yaml
├── 2026-01-27-mongodb-public-sector-summit.yaml
└── ...
```

### 2. YAML Format

```yaml
title: Focus Flow: Coworking Session (Refresh DC)
date: '2026-01-16'
time: '21:00'              # Optional, 24-hour format
url: https://www.eventbrite.com/e/...
location: Washington, DC
submitted_by: rosskarchner  # Optional
submitter_link: ''          # Optional
cost: 'Free'                # Optional
description: '...'          # Optional
end_date: '2026-01-17'      # Optional, for multi-day events
end_time: '23:00'           # Optional
```

**Required fields:**
- `title`
- `date` (YYYY-MM-DD format)

**Optional fields:**
- `time` (HH:MM in 24-hour format)
- `end_date`, `end_time` (for multi-day events)
- `url`, `location`, `cost`, `description`
- `submitted_by`, `submitter_link` (submitter attribution)

### 3. Deployment Flow

```
Local Repository
    ↓
_single_events/*.yaml
    ↓
CDK Deploy (ApplicationStack)
    ↓
S3 Bucket (single_events/ prefix)
    ↓
Event Collection Lambda (daily)
    ↓
DynamoDB Events Table
    ↓
Chalice API → Users
```

### 4. Event Collection Process

The Event Collection Lambda (`lambda/event-collection/refresh_calendars.py`) runs daily and:

1. **Loads single events from S3**
   - Lists all YAML files in `single_events/` prefix
   - Downloads and parses each YAML file

2. **Parses event data**
   - Validates required fields (title, date)
   - Parses date/time (supports all-day and timed events)
   - Extracts location info (city, state)
   - Determines location type (virtual vs in-person)
   - Generates unique event_id

3. **Stores in DynamoDB**
   - Creates or updates event in Events table
   - Sets `source_type='single_event'`
   - Sets `group_id='single_events'`
   - Sets `group_name='Community Submitted'`
   - Applies TTL (7 days after event end)

### 5. DynamoDB Attributes

Single events are stored with these special attributes:

```json
{
  "event_id": "abc123...",
  "source_type": "single_event",      // ← Identifies as single event
  "group_id": "single_events",        // ← Special group ID
  "group_name": "Community Submitted", // ← Display name
  "submitted_by": "rosskarchner",     // ← Optional submitter
  "submitter_link": "",               // ← Optional link
  // ... all other standard event fields
}
```

## Differences from iCal Events

| Feature | iCal Events | Single Events |
|---------|-------------|---------------|
| **Source** | Group iCal feeds | YAML files in repo |
| **Recurring** | Yes (expanded 60 days) | No |
| **"Last Seen" Logic** | Yes | No (always refreshed) |
| **Date Limits** | 90 days for API queries | No limits |
| **State Filter** | DC/MD/VA only | All locations |
| **Group** | From iCal feed | "Community Submitted" |
| **Auto-Discovery** | Yes (from feed) | No (manual YAML creation) |

## API Queries

Single events appear in all standard API endpoints:

```bash
# All events (includes single events)
GET /api/events

# Filter by group (only single events)
GET /api/groups/single_events

# Upcoming events (includes single events)
GET /api/events/upcoming

# Virtual events (if location is virtual)
GET /api/events/virtual
```

## Adding New Single Events

### Via Repository (Preferred)

1. Create YAML file in `_single_events/`:
   ```bash
   # Filename format: YYYY-MM-DD-event-slug.yaml
   touch _single_events/2026-02-15-new-tech-conference.yaml
   ```

2. Add event details:
   ```yaml
   title: New Tech Conference 2026
   date: '2026-02-15'
   time: '09:00'
   end_date: '2026-02-16'
   end_time: '17:00'
   location: Washington, DC
   url: https://example.com/conference
   cost: '$299'
   description: 'A two-day technology conference'
   submitted_by: 'Jane Doe'
   ```

3. Commit and deploy:
   ```bash
   git add _single_events/2026-02-15-new-tech-conference.yaml
   git commit -m "Add New Tech Conference 2026"
   git push

   # Deploy to sync S3
   cd infrastructure
   cdk deploy DCTechEvents-Application-prod
   ```

4. Trigger event collection:
   ```bash
   make refresh
   # Or wait for daily scheduled run
   ```

### Via GitHub Pull Request

Users can submit events via PR:

1. Fork repository
2. Add YAML file to `_single_events/`
3. Submit pull request
4. After merge, CDK deployment syncs to S3
5. Daily Lambda run adds to DynamoDB

## Event Lifecycle

### Creation
```
YAML file added → Deployed to S3 → Lambda processes → Stored in DynamoDB
```

### Updates
```
YAML file modified → Deployed to S3 → Lambda processes → Updated in DynamoDB
```

### Deletion
```
YAML file removed → Deployed to S3 → Event not refreshed → TTL deletes after 7 days
```

**Note**: Single events don't have "last seen" logic. They're always refreshed from S3, so removing the YAML file means the event won't be refreshed and TTL will eventually delete it.

## Validation

Before deployment, validate single event YAML files:

```bash
# Using Make
make validate-groups  # Also validates single events

# Manual validation
python3 -c "import yaml, sys, pathlib; \
  files = list(pathlib.Path('_single_events').glob('*.yaml')); \
  errors = []; \
  for f in files: \
    try: \
      data = yaml.safe_load(open(f)); \
      if not data.get('title'): errors.append(f'{f.name}: missing title'); \
      if not data.get('date'): errors.append(f'{f.name}: missing date'); \
    except Exception as e: errors.append(f'{f.name}: {e}'); \
  print('\\n'.join(errors) if errors else 'All valid'); \
  sys.exit(1 if errors else 0)"
```

## Monitoring

### Check Single Events Processing

```bash
# View Lambda logs
make logs-collection

# Look for:
# "Processing single events..."
# "Processed X single events"
```

### Query Single Events in DynamoDB

```bash
# Count single events
aws dynamodb query \
  --table-name DCTechEvents-Events-prod \
  --index-name GroupIndex \
  --key-condition-expression "group_id = :gid" \
  --expression-attribute-values '{":gid":{"S":"single_events"}}' \
  --select COUNT

# List single events
aws dynamodb query \
  --table-name DCTechEvents-Events-prod \
  --index-name GroupIndex \
  --key-condition-expression "group_id = :gid" \
  --expression-attribute-values '{":gid":{"S":"single_events"}}' \
  --max-items 10
```

### API Query

```bash
# Get single events via API
curl https://YOUR_CLOUDFRONT_URL/api/groups/single_events | jq
```

## Troubleshooting

### Issue: Single event not appearing

**Causes:**
1. YAML file not deployed to S3
2. Lambda hasn't run yet
3. Event date is in the past (with expired TTL)
4. YAML format error

**Solutions:**
```bash
# 1. Check S3
aws s3 ls s3://dctechevents-assets-prod/single_events/

# 2. Trigger Lambda manually
make refresh

# 3. Check event date
cat _single_events/YOUR_EVENT.yaml | grep date

# 4. Validate YAML
python3 -c "import yaml; yaml.safe_load(open('_single_events/YOUR_EVENT.yaml'))"
```

### Issue: Single event has wrong data

**Solution:**
1. Edit YAML file locally
2. Redeploy: `cd infrastructure && cdk deploy DCTechEvents-Application-prod`
3. Refresh: `make refresh`
4. Verify: `curl https://YOUR_API/api/groups/single_events`

### Issue: Old single events not removed

**Explanation:** Events with expired TTL are automatically deleted by DynamoDB (7 days after end_date).

**Manual cleanup:**
```bash
# Query old events
aws dynamodb scan \
  --table-name DCTechEvents-Events-prod \
  --filter-expression "source_type = :type AND #ttl < :now" \
  --expression-attribute-names '{"#ttl":"ttl"}' \
  --expression-attribute-values '{":type":{"S":"single_event"},":now":{"N":"'$(date +%s)'"}}'
```

## Best Practices

1. **Filename Convention**: Use `YYYY-MM-DD-event-slug.yaml` format
2. **Date Format**: Always use `'YYYY-MM-DD'` (quoted) for dates
3. **Time Format**: Use 24-hour format `'HH:MM'` (e.g., `'14:30'` for 2:30 PM)
4. **Location**: Be specific (e.g., "Washington, DC" not just "DC")
5. **URL**: Include full event URL for registration/details
6. **Submitter Attribution**: Credit the submitter for community-submitted events
7. **Validation**: Always validate YAML before committing
8. **Deployment**: Deploy infrastructure after adding/modifying single events

## Summary

Single events are **first-class citizens** in the serverless architecture:

✓ Stored alongside iCal events in DynamoDB
✓ Queryable via same API endpoints
✓ Same TTL cleanup (7 days after event)
✓ Automatic deployment via CDK
✓ Daily refresh from S3
✓ Supports all event features (multi-day, virtual, cost, etc.)
✓ Submitter attribution tracking
✓ No special handling needed by API consumers

The only difference is the source (`single_event` vs `ical`) and the special group ID (`single_events` vs actual group ID).
