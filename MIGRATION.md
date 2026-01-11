# Migration Guide: Flask + YAML → Chalice + DynamoDB

This guide covers migrating from the Flask-based static site to the serverless Chalice + DynamoDB architecture.

## Overview of Changes

### Before (Flask + YAML)
```
Flask App (app.py)
    ↓
Frozen-Flask (freeze.py)
    ↓
Static Site (build/)
    ↓
GitHub Pages
```

**Data Flow:**
1. `refresh_calendars.py` → Fetch iCal feeds → Cache as JSON in `_cache/`
2. `generate_month_data.py` → Merge cached events → Generate `_data/upcoming.yaml`
3. `app.py` (Flask) → Read `upcoming.yaml` → Render HTML templates
4. `freeze.py` → Generate static HTML → Deploy to GitHub Pages

### After (Chalice + DynamoDB)
```
User → CloudFront → API Gateway → Lambda (Chalice) → DynamoDB
                                   EventBridge → Lambda (Event Collection) → DynamoDB
```

**Data Flow:**
1. EventBridge (daily) → Event Collection Lambda → Fetch iCal feeds → Write to DynamoDB
2. User request → CloudFront (CDN) → API Gateway → Chalice Lambda → Query DynamoDB → Return JSON

## Key Architectural Differences

| Component | Old | New |
|-----------|-----|-----|
| **Web Framework** | Flask | Chalice (serverless) |
| **Hosting** | GitHub Pages (static) | AWS Lambda + API Gateway |
| **Data Storage** | YAML files | DynamoDB |
| **CDN** | None (GitHub Pages CDN) | CloudFront |
| **Event Collection** | Cron script | Scheduled Lambda |
| **Rendering** | Server-side (Jinja2) | API-first (JSON) |
| **Deployment** | Git push → GitHub Actions → Static build | CDK → AWS Infrastructure |

## Migration Steps

### Phase 1: Infrastructure Setup (Day 1)

#### 1.1 Deploy AWS Infrastructure

```bash
# Bootstrap CDK
cd infrastructure
cdk bootstrap

# Deploy all stacks
cdk deploy --all
```

**Outputs to save:**
- API Gateway URL
- CloudFront distribution URL
- DynamoDB table name
- S3 bucket name

#### 1.2 Verify Infrastructure

```bash
# Check DynamoDB table
aws dynamodb describe-table --table-name DCTechEvents-Events-prod

# Check S3 bucket
aws s3 ls s3://dctechevents-assets-prod/groups/

# Check Lambda functions
aws lambda list-functions | grep DCTechEvents
```

### Phase 2: Data Migration (Day 1-2)

#### 2.1 Initial Event Collection

Trigger the event collection Lambda to populate DynamoDB:

```bash
FUNCTION_NAME=$(aws lambda list-functions --query "Functions[?starts_with(FunctionName, 'DCTechEvents-EventCollection')].FunctionName" --output text)

# Invoke
aws lambda invoke --function-name $FUNCTION_NAME --invocation-type Event /tmp/response.json

# Monitor logs
aws logs tail /aws/lambda/$FUNCTION_NAME --follow
```

Wait 10-15 minutes for all groups to be processed.

#### 2.2 Verify Data in DynamoDB

```bash
# Count events
aws dynamodb scan \
  --table-name DCTechEvents-Events-prod \
  --select COUNT

# Sample events
aws dynamodb query \
  --table-name DCTechEvents-Events-prod \
  --index-name DateIndex \
  --key-condition-expression "state = :state AND start_datetime >= :start" \
  --expression-attribute-values '{":state":{"S":"DC"},":start":{"S":"2026-01-01"}}' \
  --max-items 5
```

#### 2.3 Compare Event Counts

**Old system:**
```bash
# Count events in YAML
python3 -c "import yaml; events = yaml.safe_load(open('_data/upcoming.yaml')); print(f'YAML events: {len(events)}')"
```

**New system:**
```bash
# Count events in DynamoDB
aws dynamodb scan \
  --table-name DCTechEvents-Events-prod \
  --select COUNT \
  --query 'Count'
```

**Expected**: Counts should be similar (±10% due to timing differences)

### Phase 3: Parallel Testing (Day 2-7)

Run both systems in parallel to verify parity.

#### 3.1 Test API Endpoints

```bash
# Get CloudFront URL
CLOUDFRONT_URL=$(aws cloudformation describe-stacks \
  --stack-name DCTechEvents-Distribution-prod \
  --query "Stacks[0].Outputs[?OutputKey=='DistributionDomain'].OutputValue" \
  --output text)

# Test all endpoints
curl https://$CLOUDFRONT_URL/health
curl https://$CLOUDFRONT_URL/api/events/upcoming | jq
curl https://$CLOUDFRONT_URL/api/events/virtual | jq
curl https://$CLOUDFRONT_URL/api/groups | jq
curl https://$CLOUDFRONT_URL/events.ics
```

#### 3.2 Compare Outputs

**Old system (YAML):**
```bash
cat _data/upcoming.yaml
```

**New system (DynamoDB via API):**
```bash
curl https://$CLOUDFRONT_URL/api/events | jq '.events'
```

#### 3.3 Test "Last Seen" Logic

1. **Remove an event** from a test group's iCal feed
2. **Wait for refresh** (or manually trigger Lambda)
3. **Verify** event still appears (if it's today)
4. **Next day**, verify event is gone

### Phase 4: Frontend Migration (Day 7-14)

The new architecture is API-first. You have two options:

#### Option A: Build New Frontend (Recommended)

Create a modern frontend (React, Vue, Svelte) that consumes the API:

```bash
# Example: React app
npx create-react-app dctech-events-frontend
cd dctech-events-frontend

# Install dependencies
npm install axios date-fns

# Create components
# - EventsList.jsx
# - EventCard.jsx
# - FilterBar.jsx
```

**Deploy frontend to:**
- S3 + CloudFront (static hosting)
- Vercel / Netlify
- Amplify Hosting

#### Option B: Server-Side Rendering (SSR)

Add Jinja2 template rendering to Chalice app:

```python
# In chalice-app/app.py
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('templates'))

@app.route('/')
def index():
    template = env.get_template('index.html')
    events = get_upcoming_events()
    days = prepare_events_by_day(events, local_tz)
    html = template.render(days=days)
    return Response(body=html, status_code=200, headers={'Content-Type': 'text/html'})
```

**Note**: This adds complexity and cold start time. Option A is preferred.

### Phase 5: DNS Cutover (Day 14+)

Once parallel testing is complete and frontend is ready:

#### 5.1 Update DNS

**Old DNS (GitHub Pages):**
```
dctech.events CNAME rosskarchner.github.io
```

**New DNS (CloudFront):**
```
dctech.events CNAME d111111abcdef8.cloudfront.net
```

**Steps:**
1. Lower TTL to 300 seconds (5 minutes) 24 hours before cutover
2. Update CNAME record to point to CloudFront
3. Wait for DNS propagation (5-60 minutes)
4. Verify: `dig dctech.events`

#### 5.2 Test Production

```bash
curl https://dctech.events/health
curl https://dctech.events/api/events
```

#### 5.3 Monitor

Watch CloudWatch metrics for:
- Lambda errors
- API Gateway 5xx errors
- CloudFront cache hit rate

### Phase 6: Decommission Old System (Day 15+)

Once new system is stable:

#### 6.1 Archive Old Code

```bash
git checkout -b archive/flask-app
git push origin archive/flask-app
```

#### 6.2 Keep Historical Files

Preserve these for reference:
- `_groups/` - Group definitions (now in S3)
- `config.yaml` - Configuration
- `location_utils.py` - Location parsing (may reuse)

#### 6.3 Remove Old Files (Optional)

```bash
# Remove after confirming not needed
rm -rf build/
rm -rf _cache/
rm app.py freeze.py refresh_calendars.py generate_month_data.py
```

#### 6.4 Update GitHub Actions

Remove or disable old deployment workflows:
- `.github/workflows/deploy.yml` (Flask build)

Keep:
- `.github/workflows/test.yml` (unit tests)

Add new workflow for CDK deployment (optional):
```yaml
# .github/workflows/deploy-cdk.yml
name: Deploy Infrastructure
on:
  push:
    branches: [main]
    paths:
      - 'infrastructure/**'
      - 'chalice-app/**'
      - 'lambda/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - uses: actions/setup-python@v4
      - name: Install CDK
        run: npm install -g aws-cdk
      - name: Deploy
        run: |
          cd infrastructure
          pip install -r requirements.txt
          cdk deploy --all --require-approval never
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

## Data Model Mapping

### YAML Event → DynamoDB Event

**Old (YAML):**
```yaml
- title: "Tech Meetup"
  date: "2026-01-15"
  time: "19:00"
  location: "Washington, DC"
  url: "https://example.com/event"
  group: "DC Tech"
  group_website: "https://dctech.org"
```

**New (DynamoDB):**
```json
{
  "event_id": "abc123...",
  "start_datetime": "2026-01-15T19:00:00-05:00",
  "end_datetime": "2026-01-15T21:00:00-05:00",
  "title": "Tech Meetup",
  "location": "Washington, DC",
  "city": "Washington",
  "state": "DC",
  "location_type": "in_person",
  "url": "https://example.com/event",
  "group_id": "dc-tech",
  "group_name": "DC Tech",
  "group_website": "https://dctech.org",
  "source_type": "ical",
  "last_seen_date": "2026-01-10",
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-10T00:00:00Z",
  "ttl": 1738281600
}
```

**Key differences:**
- `date` + `time` → `start_datetime` (ISO 8601)
- Added: `event_id`, `state`, `location_type`, `last_seen_date`, `ttl`
- Timestamps are ISO 8601 with timezone

## API Endpoint Mapping

| Old Route | New API Endpoint |
|-----------|------------------|
| `/` | `/api/events/upcoming` |
| `/virtual/` | `/api/events/virtual` |
| `/week/<week_id>/` | `/api/events/week/<week_id>` |
| `/locations/` | `/api/locations` |
| `/locations/<state>/` | `/api/locations/<state>` |
| `/groups/` | `/api/groups` |
| `/events.ics` | `/events.ics` (unchanged) |
| `/sitemap.xml` | `/sitemap.xml` (unchanged) |

## "Last Seen" Logic Comparison

### Old (File-based)

```python
# refresh_calendars.py (lines 365-379)
today_str = datetime.now(local_tz).strftime('%Y-%m-%d')
remembered_events = [e for e in existing_events if e.get('start_date') == today_str]

if remembered_events:
    events_map = {}
    for e in remembered_events:
        key = (e.get('url'), e.get('title'), e.get('start_date'), e.get('start_time'))
        events_map[key] = e
    for e in events:
        key = (e.get('url'), e.get('title'), e.get('start_date'), e.get('start_time'))
        events_map[key] = e
    events = list(events_map.values())
```

### New (DynamoDB)

```python
# lambda/event-collection/refresh_calendars.py (lines 370-395)
for event_id, existing in existing_events_map.items():
    if event_id not in new_events_map:
        start_date = existing.get('start_datetime', '').split('T')[0]
        last_seen = existing.get('last_seen_date', '')

        # Preserve today's events (memory logic)
        if start_date == today:
            table.update_item(
                Key={'event_id': existing['event_id'], 'start_datetime': existing['start_datetime']},
                UpdateExpression='SET last_seen_date = :today, updated_at = :now',
                ExpressionAttributeValues={':today': today, ':now': datetime.now(timezone.utc).isoformat()}
            )
```

**Both implementations:**
- Preserve events scheduled for today
- Deduplicate by event key
- Merge new and remembered events

## Testing Checklist

- [ ] All groups loaded from S3
- [ ] Events populating in DynamoDB
- [ ] Event count matches YAML ±10%
- [ ] "Last seen" logic preserves today's events
- [ ] TTL set correctly (7 days after event end)
- [ ] API endpoints return correct data
- [ ] CloudFront caching working
- [ ] iCal feed exports correctly
- [ ] Virtual events filtered correctly
- [ ] State filtering (DC/MD/VA) works
- [ ] Week filtering works
- [ ] Group-specific queries work
- [ ] Health check endpoint responds
- [ ] Sitemap generates correctly

## Rollback Plan

If issues arise, you can quickly rollback:

### Quick Rollback (DNS)

```bash
# Point DNS back to GitHub Pages
dctech.events CNAME rosskarchner.github.io
```

Rollback time: 5-60 minutes (DNS propagation)

### Infrastructure Rollback

```bash
# Destroy new infrastructure
cd infrastructure
cdk destroy --all

# Redeploy old system
cd ..
make freeze
git push origin main
```

## Common Issues and Solutions

### Issue: Event count mismatch

**Solution:**
- Wait for full iCal refresh (15 minutes)
- Check for failed Lambda invocations
- Verify group YAML files uploaded to S3

### Issue: CloudFront serving stale data

**Solution:**
```bash
# Invalidate cache
DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
  --stack-name DCTechEvents-Distribution-prod \
  --query "Stacks[0].Outputs[?OutputKey=='DistributionId'].OutputValue" \
  --output text)

aws cloudfront create-invalidation \
  --distribution-id $DISTRIBUTION_ID \
  --paths "/*"
```

### Issue: Lambda timeout during event collection

**Solution:**
- Increase timeout in `scheduler_stack.py`
- Reduce date range (60 days → 30 days)
- Split processing across multiple invocations

### Issue: DynamoDB throttling

**Solution:**
- Check CloudWatch metrics
- Enable on-demand mode (already default)
- Add retry logic with exponential backoff

## Post-Migration Monitoring

### Week 1: Daily Checks

- [ ] Review CloudWatch logs for errors
- [ ] Monitor DynamoDB read/write capacity
- [ ] Check CloudFront cache hit rate (should be >80%)
- [ ] Verify event collection Lambda runs daily
- [ ] Compare event counts with old system

### Week 2-4: Weekly Checks

- [ ] Review cost in AWS Cost Explorer
- [ ] Monitor API latency (should be <500ms)
- [ ] Check TTL deletions working correctly
- [ ] Verify no orphaned events in database

### Month 2+: Monthly Checks

- [ ] Review and optimize costs
- [ ] Update dependencies
- [ ] Plan feature enhancements

## Next Steps After Migration

1. **Frontend Development** - Build React/Vue app
2. **Event Submission** - Implement POST /api/events endpoint
3. **OAuth Integration** - GitHub OAuth for submissions
4. **Search** - Add full-text search with OpenSearch
5. **Analytics** - Track popular events
6. **Notifications** - Email/SMS reminders
7. **API Keys** - For external integrations

## Support

For migration assistance:
- GitHub Issues: https://github.com/rosskarchner/dctech.events/issues
- AWS Support: https://console.aws.amazon.com/support/
