# DC Tech Events - Serverless Architecture

AWS serverless implementation of DC Tech Events using DynamoDB, Lambda, API Gateway, and CloudFront.

## 🏗️ Architecture

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │
       ↓
┌──────────────────┐     ┌─────────────────┐
│   CloudFront     │────→│   S3 Bucket     │
│   (CDN)          │     │  (Static Assets) │
└──────┬───────────┘     └─────────────────┘
       │
       ↓
┌──────────────────┐
│  API Gateway     │
└──────┬───────────┘
       │
       ↓
┌──────────────────┐     ┌─────────────────┐
│  Lambda          │────→│   DynamoDB      │
│  (Chalice App)   │     │  (Events Table)  │
└──────────────────┘     └─────────────────┘

┌──────────────────┐
│  EventBridge     │
│  (Daily 2 AM)    │
└──────┬───────────┘
       │
       ↓
┌──────────────────┐     ┌─────────────────┐
│  Lambda          │────→│   DynamoDB      │
│  (Event Collect) │     │  (Events Table)  │
└──────┬───────────┘     └─────────────────┘
       │
       ↓
┌──────────────────┐
│  S3 Bucket       │
│  (Groups YAML)   │
└──────────────────┘
```

## 📁 Project Structure

```
dctech.events/
├── infrastructure/              # AWS CDK Infrastructure
│   ├── app.py                  # CDK app entry point
│   ├── cdk.json                # CDK configuration
│   ├── requirements.txt        # CDK dependencies
│   └── stacks/
│       ├── database_stack.py   # DynamoDB table
│       ├── application_stack.py # Chalice API
│       ├── scheduler_stack.py  # Event collection
│       └── distribution_stack.py # CloudFront CDN
│
├── chalice-app/                 # Chalice API Application
│   ├── app.py                  # Main Chalice routes
│   ├── requirements.txt        # Python dependencies
│   ├── .chalice/
│   │   └── config.json         # Chalice configuration
│   └── chalicelib/
│       ├── dynamodb.py         # DynamoDB operations
│       ├── event_utils.py      # Event processing
│       ├── groups.py           # Groups management
│       └── ical_export.py      # iCal generation
│
├── lambda/                      # Lambda Functions
│   └── event-collection/
│       ├── refresh_calendars.py # Event collection logic
│       └── requirements.txt    # Lambda dependencies
│
├── _groups/                     # Group definitions (synced to S3)
│   └── *.yaml                  # Individual group files
│
├── ARCHITECTURE.md              # Architecture documentation
├── DEPLOYMENT.md                # Deployment guide
├── MIGRATION.md                 # Migration guide
└── README-SERVERLESS.md         # This file
```

## 🚀 Quick Start

### Prerequisites

```bash
# Install AWS CDK
npm install -g aws-cdk

# Configure AWS credentials
aws configure
```

### Deploy

```bash
# 1. Bootstrap CDK (first time only)
cd infrastructure
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export CDK_DEFAULT_REGION=us-east-1
cdk bootstrap

# 2. Deploy all stacks
pip install -r requirements.txt
cdk deploy --all

# 3. Trigger initial data load
FUNCTION_NAME=$(aws lambda list-functions --query "Functions[?starts_with(FunctionName, 'DCTechEvents-EventCollection')].FunctionName" --output text)
aws lambda invoke --function-name $FUNCTION_NAME --invocation-type Event /tmp/response.json

# 4. Get API URL
aws cloudformation describe-stacks \
  --stack-name DCTechEvents-Distribution-prod \
  --query "Stacks[0].Outputs[?OutputKey=='DistributionDomain'].OutputValue" \
  --output text
```

### Test

```bash
# Set CloudFront URL
export CLOUDFRONT_URL=d111111abcdef8.cloudfront.net

# Test endpoints
curl https://$CLOUDFRONT_URL/health
curl https://$CLOUDFRONT_URL/api/events/upcoming
curl https://$CLOUDFRONT_URL/api/groups
```

## 📊 DynamoDB Schema

### Events Table

**Primary Key:**
- Partition Key: `event_id` (String) - SHA256 hash
- Sort Key: `start_datetime` (String) - ISO 8601

**Global Secondary Indexes:**
1. **DateIndex** - Query by state and date
   - PK: `state` (DC/MD/VA/ALL)
   - SK: `start_datetime`

2. **GroupIndex** - Query by group
   - PK: `group_id`
   - SK: `start_datetime`

3. **LocationTypeIndex** - Query by location type
   - PK: `location_type` (virtual/in_person)
   - SK: `start_datetime`

**TTL:** `ttl` field (auto-delete 7 days after event end)

### Event Attributes

```json
{
  "event_id": "abc123...",
  "start_datetime": "2026-01-15T19:00:00-05:00",
  "end_datetime": "2026-01-15T21:00:00-05:00",
  "title": "Tech Meetup",
  "description": "...",
  "url": "https://example.com/event",
  "location": "Washington, DC",
  "city": "Washington",
  "state": "DC",
  "location_type": "in_person",
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

## 🔄 "Last Seen" Logic

Events don't disappear immediately when removed from iCal feeds:

1. **Event still in feed** → Update `last_seen_date = today`
2. **Event missing from feed:**
   - If `start_date == today` → **Keep** (preserve today's events)
   - If `last_seen_date >= yesterday` → **Keep** (grace period)
   - If event past + `last_seen_date < yesterday` → **TTL deletes**

This prevents events from disappearing during the day due to feed issues.

## 🌐 API Endpoints

### Events

| Endpoint | Description | Query Params |
|----------|-------------|--------------|
| `GET /api/events` | All events with filters | `state`, `location_type`, `group_id`, `limit` |
| `GET /api/events/upcoming` | Upcoming in-person events by day | - |
| `GET /api/events/virtual` | Upcoming virtual events by day | - |
| `GET /api/events/week/{week_id}` | Events for ISO week | - |

### Locations

| Endpoint | Description |
|----------|-------------|
| `GET /api/locations` | Event counts by state |
| `GET /api/locations/{state}` | Events for DC/MD/VA |

### Groups

| Endpoint | Description |
|----------|-------------|
| `GET /api/groups` | All approved groups |
| `GET /api/groups/{group_id}` | Events for specific group |

### Other

| Endpoint | Description |
|----------|-------------|
| `GET /events.ics` | iCal feed |
| `GET /sitemap.xml` | XML sitemap |
| `GET /health` | Health check |

## 📦 Event Collection Process

Runs daily at 2 AM UTC via EventBridge:

1. **Load groups** from S3 (`_groups/*.yaml`)
2. **For each active group with iCal feed:**
   - Fetch iCal with HTTP caching
   - Parse and expand recurring events (60 days)
   - Extract event details
   - Determine location type (virtual/in-person)
   - Extract city/state
3. **Query existing events** from DynamoDB (by group)
4. **Implement "last seen" logic:**
   - Update `last_seen_date` for events still in feed
   - Preserve today's events even if missing from feed
   - Let TTL handle cleanup of old events
5. **Write to DynamoDB** (batch write for performance)

## 🔧 Development

### Local Development (Chalice)

```bash
cd chalice-app
pip install -r requirements.txt

# Set environment variables
export DYNAMODB_TABLE_NAME=DCTechEvents-Events-prod
export ASSETS_BUCKET=dctechevents-assets-prod
export AWS_DEFAULT_REGION=us-east-1

# Run locally
chalice local --port 8000

# Test
curl http://localhost:8000/health
```

### Local Development (Event Collection)

```bash
cd lambda/event-collection
pip install -r requirements.txt

# Set environment variables
export DYNAMODB_TABLE_NAME=DCTechEvents-Events-prod
export ASSETS_BUCKET=dctechevents-assets-prod

# Test locally
python refresh_calendars.py
```

### Deploy Changes

**Infrastructure changes:**
```bash
cd infrastructure
cdk diff
cdk deploy --all
```

**Chalice app changes:**
```bash
cd infrastructure
cdk deploy DCTechEvents-Application-prod
```

**Event collection changes:**
```bash
cd infrastructure
cdk deploy DCTechEvents-Scheduler-prod
```

**Group definitions:**
```bash
# Edit _groups/*.yaml
cd infrastructure
cdk deploy DCTechEvents-Application-prod  # Syncs to S3
```

## 📈 Monitoring

### CloudWatch Logs

```bash
# Event collection Lambda
aws logs tail /aws/lambda/DCTechEvents-EventCollection-prod --follow

# Chalice API Lambda
aws logs tail /aws/lambda/dctech-events-prod --follow
```

### CloudWatch Metrics

- **Lambda**: Invocations, Duration, Errors, Throttles
- **DynamoDB**: Read/Write capacity, Throttles
- **API Gateway**: Requests, Latency, 4XX/5XX
- **CloudFront**: Requests, Cache hit rate, Error rate

### DynamoDB Queries

```bash
# Count events
aws dynamodb scan \
  --table-name DCTechEvents-Events-prod \
  --select COUNT

# Query upcoming DC events
aws dynamodb query \
  --table-name DCTechEvents-Events-prod \
  --index-name DateIndex \
  --key-condition-expression "state = :state AND start_datetime >= :start" \
  --expression-attribute-values '{":state":{"S":"DC"},":start":{"S":"2026-01-01"}}'
```

## 💰 Cost Breakdown

Based on moderate traffic (100K requests/month):

| Service | Usage | Cost |
|---------|-------|------|
| DynamoDB | 10 MB storage + on-demand | $0.25 |
| Lambda (API) | 100K invocations × 100ms | $0.20 |
| Lambda (Collection) | 30 invocations × 5 min | $0.00 |
| API Gateway | 100K requests | $0.35 |
| CloudFront | 100K requests + 100 GB | $8.60 |
| S3 | 1 GB storage + requests | $0.50 |
| **Total** | | **~$10-15/month** |

Free tier covers much of this for first 12 months.

## 🔒 Security

- ✅ **HTTPS only** (CloudFront enforces)
- ✅ **IAM roles** (no hardcoded credentials)
- ✅ **DynamoDB encryption** at rest (default)
- ✅ **S3 bucket** private (no public access)
- ✅ **Lambda** in VPC (optional, for extra security)
- ✅ **API Gateway** throttling (10,000 req/sec default)

## 🐛 Troubleshooting

### No events showing

```bash
# Check if event collection ran
aws logs tail /aws/lambda/DCTechEvents-EventCollection-prod

# Manually trigger
FUNCTION_NAME=DCTechEvents-EventCollection-prod
aws lambda invoke --function-name $FUNCTION_NAME --invocation-type Event /tmp/response.json
```

### CloudFront serving stale data

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

### Lambda timeout

```bash
# Increase timeout in scheduler_stack.py
timeout=Duration.minutes(15),  # Increase as needed

# Redeploy
cd infrastructure
cdk deploy DCTechEvents-Scheduler-prod
```

## 📚 Documentation

- [Architecture](./ARCHITECTURE.md) - Detailed architecture documentation
- [Deployment](./DEPLOYMENT.md) - Complete deployment guide
- [Migration](./MIGRATION.md) - Migration from Flask to Chalice
- [Chalice App](./chalice-app/README.md) - Chalice API documentation
- [Infrastructure](./infrastructure/README.md) - CDK infrastructure guide

## 🎯 Next Steps

- [ ] Build frontend (React/Vue)
- [ ] Add event submission API
- [ ] Implement OAuth authentication
- [ ] Add full-text search (OpenSearch)
- [ ] Set up monitoring alarms
- [ ] Configure custom domain
- [ ] Implement rate limiting
- [ ] Add analytics

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes
4. Test locally
5. Deploy to dev environment
6. Submit pull request

## 📄 License

[Same as original repository]

## 🆘 Support

- GitHub Issues: https://github.com/rosskarchner/dctech.events/issues
- Documentation: See `ARCHITECTURE.md`, `DEPLOYMENT.md`, `MIGRATION.md`
