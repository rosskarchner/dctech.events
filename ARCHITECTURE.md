# DC Tech Events - DynamoDB + Chalice Architecture

## Overview

Migration from Flask + YAML to Chalice + DynamoDB architecture with CloudFront CDN.

## DynamoDB Schema Design

### Events Table

**Table Name:** `DCTechEvents`

**Primary Key:**
- Partition Key: `event_id` (String) - SHA256 hash of (url, title, start_date, start_time)
- Sort Key: `start_datetime` (String) - ISO 8601 format (YYYY-MM-DDTHH:MM:SS)

**Attributes:**
- `event_id` (String, PK) - Unique event identifier
- `start_datetime` (String, SK) - Event start date/time in ISO 8601
- `end_datetime` (String) - Event end date/time in ISO 8601
- `title` (String) - Event title
- `description` (String) - Event description
- `url` (String) - Event URL
- `location` (String) - Physical location or "Virtual"
- `location_type` (String) - "in_person" or "virtual"
- `city` (String) - Extracted city
- `state` (String) - Extracted state (DC/MD/VA)
- `group_id` (String) - Organizing group ID
- `group_name` (String) - Organizing group name
- `group_website` (String) - Group website URL
- `cost` (String) - Event cost (optional)
- `source_type` (String) - "ical" or "single_event"
- `last_seen_date` (String) - ISO 8601 date when last seen in feed
- `ttl` (Number) - Unix timestamp for DynamoDB TTL (auto-deletion)
- `created_at` (String) - ISO 8601 timestamp when first added
- `updated_at` (String) - ISO 8601 timestamp when last updated
- `submitted_by` (String) - Optional submitter name
- `also_published_by` (List) - Cross-posting information

**Global Secondary Indexes:**

1. **DateIndex** (for upcoming events queries)
   - Partition Key: `state` (String) - DC/MD/VA/ALL
   - Sort Key: `start_datetime` (String)
   - Projection: ALL

2. **GroupIndex** (for group-specific queries)
   - Partition Key: `group_id` (String)
   - Sort Key: `start_datetime` (String)
   - Projection: ALL

**TTL Configuration:**
- TTL Attribute: `ttl`
- Events are automatically deleted 7 days after their end_datetime

### "Last Seen" Logic Implementation

**Event Lifecycle:**
1. **First Seen**: Event appears in iCal feed
   - Create DynamoDB item with `created_at`, `last_seen_date = today`
   - Set `ttl = end_datetime + 7 days`

2. **Still in Feed**: Event refreshed and still in iCal feed
   - Update `last_seen_date = today`
   - Update `updated_at = now`
   - Refresh `ttl = end_datetime + 7 days`

3. **Missing from Feed**: Event not in latest iCal fetch
   - **If `start_date == today`**: Keep event (memory for today's events)
   - **If `last_seen_date >= yesterday`**: Keep event (grace period)
   - **If event past and `last_seen_date < yesterday`**: Let TTL handle deletion

4. **Auto-Cleanup**: DynamoDB TTL automatically removes events 7 days after end

**Benefits:**
- Events don't disappear immediately if temporarily removed from feed
- Same-day events are preserved (existing "memory" behavior)
- Automatic cleanup of old events via TTL
- No manual pruning required

---

## Application Architecture

### Components

1. **Chalice API Application**
   - REST API for serving events
   - Replaces Flask routes
   - Deployed as AWS Lambda + API Gateway
   - Behind CloudFront CDN

2. **Event Collection Lambda**
   - Scheduled function (runs daily)
   - Fetches iCal feeds
   - Processes events and stores in DynamoDB
   - Implements "last seen" logic

3. **CloudFront Distribution**
   - CDN for API caching
   - Custom domain support
   - SSL/TLS termination

4. **S3 Bucket**
   - Static assets (CSS, JS, images)
   - Group definitions YAML files
   - CloudFront origin

### API Endpoints (Chalice Routes)

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Homepage - upcoming in-person events |
| `/virtual` | GET | Virtual events only |
| `/week/{week_id}` | GET | Events for specific ISO week |
| `/locations` | GET | Event count by region |
| `/locations/{state}` | GET | Events in DC/VA/MD |
| `/groups` | GET | Approved groups list |
| `/events.ics` | GET | iCal feed export |
| `/api/events` | GET | JSON API for events (with filters) |

**Query Parameters:**
- `?state=DC|MD|VA` - Filter by state
- `?location_type=virtual|in_person` - Filter by location type
- `?start_date=YYYY-MM-DD` - Events after date
- `?end_date=YYYY-MM-DD` - Events before date
- `?group_id=xxx` - Events by group
- `?limit=50` - Result limit

### Data Flow

```
iCal Feeds → Event Collection Lambda → DynamoDB
                                          ↓
                   User → CloudFront → API Gateway → Chalice Lambda → DynamoDB
                              ↓
                         S3 (static assets)
```

---

## Infrastructure as Code (Python CDK)

### CDK Stacks

1. **DatabaseStack**
   - DynamoDB Events table
   - GSIs (DateIndex, GroupIndex)
   - TTL configuration

2. **ApplicationStack**
   - Chalice app deployment
   - Lambda functions
   - API Gateway
   - IAM roles and policies

3. **DistributionStack**
   - CloudFront distribution
   - S3 bucket for static assets
   - Cache behaviors
   - Custom domain (optional)

4. **SchedulerStack**
   - EventBridge rule (daily calendar refresh)
   - Lambda function for event collection

---

## Migration Strategy

### Phase 1: Infrastructure Setup
1. Deploy DynamoDB table via CDK
2. Deploy S3 bucket for static assets
3. Set up IAM roles and policies

### Phase 2: Event Collection Migration
1. Create event collection Lambda
2. Migrate refresh_calendars.py logic
3. Test DynamoDB writes
4. Deploy EventBridge scheduled rule

### Phase 3: API Migration
1. Create Chalice app structure
2. Migrate Flask routes to Chalice
3. Replace YAML reads with DynamoDB queries
4. Deploy API

### Phase 4: CDN Setup
1. Deploy CloudFront distribution
2. Configure cache behaviors
3. Update DNS (if custom domain)

### Phase 5: Testing & Cutover
1. Run both systems in parallel
2. Validate event parity
3. Update GitHub Actions workflows
4. Decommission Flask app

---

## Configuration Management

### Environment Variables

```bash
# DynamoDB
DYNAMODB_TABLE_NAME=DCTechEvents
AWS_REGION=us-east-1

# S3
STATIC_ASSETS_BUCKET=dctech-events-assets
GROUPS_BUCKET=dctech-events-groups

# API
API_STAGE=prod
CLOUDFRONT_DOMAIN=dctech.events

# OAuth (for event submission)
GITHUB_CLIENT_ID=xxx
GITHUB_CLIENT_SECRET=xxx
OAUTH_CALLBACK_URL=https://dctech.events/oauth/callback
```

### Groups Configuration

- Groups YAML files remain in `_groups/`
- Uploaded to S3 bucket
- Event collection Lambda reads from S3
- CDK handles S3 asset deployment

---

## Deployment

### Prerequisites
```bash
npm install -g aws-cdk
pip install aws-cdk-lib chalice
```

### Deploy Infrastructure
```bash
cd infrastructure
pip install -r requirements.txt
cdk bootstrap  # First time only
cdk deploy --all
```

### Deploy Chalice App
```bash
cd chalice-app
pip install -r requirements.txt
chalice deploy --stage prod
```

### Update CloudFront
```bash
cd infrastructure
cdk deploy DistributionStack
```

---

## Cost Estimation

**DynamoDB:**
- On-Demand pricing
- ~10K events × 1 KB = 10 MB storage = $0.0025/month
- Read/Write requests: ~$0.25/month for low traffic

**Lambda:**
- Event Collection: 1 invocation/day × 30s = $0.00
- API: 100K requests/month × 100ms = $0.20/month

**API Gateway:**
- 100K requests = $0.35/month

**CloudFront:**
- 100 GB data transfer = $8.50/month
- 100K requests = $0.10/month

**S3:**
- Storage: $0.023/GB/month
- Requests: Minimal

**Total Estimate:** ~$10-15/month for low-moderate traffic

---

## Benefits of New Architecture

✅ **Scalability** - Auto-scaling Lambda, DynamoDB on-demand
✅ **Performance** - CloudFront CDN, DynamoDB single-digit ms queries
✅ **Reliability** - Managed services, multi-AZ by default
✅ **Cost-Effective** - Pay per use, no idle servers
✅ **Infrastructure as Code** - Reproducible deployments via CDK
✅ **Automatic Cleanup** - DynamoDB TTL removes old events
✅ **Real-time Updates** - No static site generation delay
✅ **API-First** - JSON API for integrations

---

## Observability

### CloudWatch Metrics
- Lambda invocations, duration, errors
- DynamoDB read/write capacity, throttles
- CloudFront cache hit rate, requests
- API Gateway 4xx/5xx errors

### CloudWatch Logs
- Event collection Lambda logs
- Chalice application logs
- API Gateway access logs

### Alarms
- Lambda error rate > 5%
- DynamoDB throttling events
- API Gateway 5xx errors > 1%
