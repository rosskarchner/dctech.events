# Organization Features Integration

**NOTE: The separate organize.dctech.events site has been deprecated. All functionality is now integrated into next.dctech.events.**

## Overview

The next.dctech.events site now includes all organization features:

- **Event Management**: Users can submit events via `/submit/` which creates pull requests to the GitHub repository
- **Group Management**: Users can submit groups via `/submit-group/` 
- **Authentication**: Cognito-based authentication for submitting events and groups
- **API Endpoints**: RESTful API for events, groups, and locations
- **Auto-sync**: Lambda function syncs from GitHub repository every 4 hours

## Current Architecture

All features are served from a single CloudFront distribution with two origins:

1. **API Gateway (Lambda)**: Handles dynamic routes (/, /events, /groups, /submit/, etc.)
2. **S3**: Serves static assets (CSS, JS)

## User Features on next.dctech.events

### Public Features (No Login Required)
- Browse events at `/`
- Filter by location at `/locations/`, `/locations/dc/`, etc.
- View groups at `/groups/`
- View weekly summaries at `/week/{week-id}/`
- Access JSON API at `/events` and `/groups`

### Authenticated Features (Requires Cognito Login)
- Submit events at `/submit/` - Creates PR to `_single_events/`
- Submit groups at `/submit-group/` - Creates PR to `_groups/`

## Data Flow

```
GitHub Repository (_groups/*.yaml, _single_events/*.yaml)
         ↓
Refresh Lambda (every 4 hours)
         ↓
DynamoDB (organize-events, organize-groups tables)
         ↓
API Lambda
         ↓
Users (next.dctech.events)
```

## Deployment

The infrastructure is deployed with:

```bash
cd infrastructure
npx cdk deploy
```

This deploys:
- API Gateway + Lambda functions
- DynamoDB tables
- Cognito User Pool
- CloudFront distribution
- S3 bucket for static assets
- EventBridge rule for scheduled syncs

## Configuration

All configuration is in the CDK stack. No separate config files needed.

Environment variables set automatically:
- `EVENTS_TABLE`: DynamoDB events table name
- `GROUPS_TABLE`: DynamoDB groups table name  
- `USER_POOL_ID`: Cognito user pool ID
- `USER_POOL_CLIENT_ID`: Cognito client ID
- `GITHUB_TOKEN_SECRET`: Secrets Manager ARN for GitHub token

## Migration Notes

The original integrate with organize.dctech.events approach is no longer needed. All functionality is consolidated into next.dctech.events.
