# DC Tech Events - Chalice API

Serverless API application for DC Tech Events using AWS Chalice.

## Overview

This is a Chalice-based serverless API that replaces the Flask application. It provides:

- RESTful JSON API for events
- DynamoDB backend for event storage
- CloudFront CDN for caching
- Serverless architecture (Lambda + API Gateway)

## Prerequisites

- Python 3.11+
- AWS CLI configured with credentials
- Chalice CLI: `pip install chalice`

## Setup

1. Install dependencies:
```bash
cd chalice-app
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. Configure environment (if testing locally):
```bash
export DYNAMODB_TABLE_NAME=DCTechEvents-Events-prod
export ASSETS_BUCKET=dctechevents-assets-prod
export AWS_DEFAULT_REGION=us-east-1
```

## Local Development

Run locally with Chalice's built-in server:

```bash
chalice local --stage dev --port 8000
```

Test endpoints:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/events
curl http://localhost:8000/api/events/upcoming
```

## Deployment

### Using CDK (Recommended)

The Chalice app is deployed automatically by the CDK ApplicationStack:

```bash
cd ../infrastructure
cdk deploy DCTechEvents-Application-prod
```

### Using Chalice CLI

Alternatively, deploy directly with Chalice:

```bash
# Deploy to dev
chalice deploy --stage dev

# Deploy to prod
chalice deploy --stage prod
```

Get the deployed API URL:
```bash
chalice url --stage prod
```

## API Endpoints

### Events API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/events` | GET | Get all upcoming events (with filters) |
| `/api/events/upcoming` | GET | Get upcoming in-person events by day |
| `/api/events/virtual` | GET | Get upcoming virtual events by day |
| `/api/events/week/{week_id}` | GET | Get events for specific week |
| `/api/locations` | GET | Get event counts by location |
| `/api/locations/{state}` | GET | Get events for specific state (DC/MD/VA) |
| `/api/groups` | GET | Get all approved groups |
| `/api/groups/{group_id}` | GET | Get events for specific group |

### Other Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/events.ics` | GET | iCal feed of upcoming events |
| `/sitemap.xml` | GET | XML sitemap |
| `/health` | GET | Health check endpoint |

### Query Parameters

For `/api/events`:
- `state` - Filter by state (DC, MD, VA)
- `location_type` - Filter by type (virtual, in_person)
- `group_id` - Filter by group ID
- `start_date` - Events after date (YYYY-MM-DD)
- `end_date` - Events before date (YYYY-MM-DD)
- `limit` - Max results (default: 100)

## Example Requests

```bash
# Get all upcoming events
curl https://api.dctech.events/api/events

# Get virtual events only
curl https://api.dctech.events/api/events/virtual

# Get DC events only
curl https://api.dctech.events/api/events?state=DC

# Get events for a specific group
curl https://api.dctech.events/api/groups/refresh-dc

# Get events for week 2 of 2026
curl https://api.dctech.events/api/events/week/2026-W02

# Download iCal feed
curl https://api.dctech.events/events.ics -o events.ics
```

## Architecture

```
User Request
    ↓
CloudFront (CDN)
    ↓
API Gateway
    ↓
Lambda (Chalice App)
    ↓
DynamoDB (Events) + S3 (Groups)
```

## Environment Variables

Set by CDK during deployment:

- `DYNAMODB_TABLE_NAME` - DynamoDB events table name
- `ASSETS_BUCKET` - S3 bucket for static assets and groups
- `ENVIRONMENT` - Deployment environment (dev/prod)
- `AWS_DEFAULT_REGION` - AWS region

Optional (with defaults):
- `TIMEZONE` - Timezone (default: US/Eastern)
- `SITE_NAME` - Site name (default: DC Tech Events)
- `BASE_URL` - Base URL (default: https://dctech.events)

## Project Structure

```
chalice-app/
├── app.py                  # Main Chalice application
├── requirements.txt        # Python dependencies
├── .chalice/
│   └── config.json        # Chalice configuration
└── chalicelib/            # Application libraries
    ├── __init__.py
    ├── dynamodb.py        # DynamoDB operations
    ├── event_utils.py     # Event processing utilities
    ├── groups.py          # Groups management (S3)
    └── ical_export.py     # iCal feed generation
```

## Testing

Run unit tests:
```bash
python -m pytest tests/
```

Test against deployed API:
```bash
# Set API URL
export API_URL=$(chalice url --stage prod)

# Run tests
python -m pytest tests/integration/
```

## Monitoring

### CloudWatch Logs

View logs:
```bash
chalice logs --stage prod

# Follow logs (tail)
chalice logs --stage prod --follow
```

### CloudWatch Metrics

Monitor in AWS Console:
- Lambda: Invocations, Duration, Errors
- API Gateway: Requests, Latency, 4XX/5XX
- DynamoDB: Read/Write capacity

## Troubleshooting

### Import errors

Ensure all dependencies are in `requirements.txt`:
```bash
pip freeze > requirements.txt
```

### Permission errors

The IAM role is managed by CDK. Check `infrastructure/stacks/application_stack.py` for permissions.

### DynamoDB errors

Verify table name and region:
```bash
aws dynamodb describe-table --table-name DCTechEvents-Events-prod
```

### Cold start issues

Lambda cold starts can take 1-2 seconds. CloudFront caching helps mitigate this.

## Migration from Flask

Key differences from Flask version:

1. **No HTML rendering** - API-first design (JSON responses)
2. **No Frozen-Flask** - Dynamic serverless architecture
3. **DynamoDB** - Replaces YAML files
4. **S3 for groups** - Replaces local _groups/ directory
5. **CloudFront** - Built-in CDN
6. **Auto-scaling** - Handles traffic spikes automatically

## Cost Optimization

- API Gateway caching (via CloudFront)
- DynamoDB on-demand pricing
- Lambda provisioned concurrency (optional, for consistent latency)

## Future Enhancements

- [ ] Add event submission endpoint (POST /api/events)
- [ ] Add group submission endpoint (POST /api/groups)
- [ ] Implement OAuth for submissions
- [ ] Add full-text search (OpenSearch/Elasticsearch)
- [ ] Add newsletter generation endpoints
- [ ] Implement rate limiting
- [ ] Add API key authentication for external integrations
