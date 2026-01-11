# DC Tech Events - Infrastructure (CDK)

Python CDK infrastructure for DC Tech Events serverless application.

## Prerequisites

- AWS CLI configured with credentials
- Python 3.11+
- Node.js 18+ (for CDK CLI)
- AWS CDK CLI installed: `npm install -g aws-cdk`

## Setup

1. Install Python dependencies:
```bash
cd infrastructure
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. Bootstrap CDK (first time only):
```bash
cdk bootstrap aws://ACCOUNT-ID/REGION
```

## Deployment

### Deploy All Stacks

```bash
cdk deploy --all
```

### Deploy Individual Stacks

```bash
# Database only (DynamoDB)
cdk deploy DCTechEvents-Database-prod

# Application only (Chalice API)
cdk deploy DCTechEvents-Application-prod

# Scheduler only (Event Collection Lambda)
cdk deploy DCTechEvents-Scheduler-prod

# Distribution only (CloudFront)
cdk deploy DCTechEvents-Distribution-prod
```

### Deploy to Different Environment

```bash
cdk deploy --all --context environment=dev
```

## Stacks

### DatabaseStack
- DynamoDB Events table
- Global Secondary Indexes (DateIndex, GroupIndex, LocationTypeIndex)
- TTL configuration for automatic cleanup

### ApplicationStack
- S3 bucket for static assets and group definitions
- Chalice API deployment (Lambda + API Gateway)
- IAM roles and permissions

### SchedulerStack
- Event collection Lambda function
- EventBridge scheduled rule (daily at 2 AM UTC)
- Manual refresh Lambda function

### DistributionStack
- CloudFront distribution
- Cache policies for API and static assets
- Origin request policies

## CDK Commands

```bash
# List all stacks
cdk list

# Synthesize CloudFormation templates
cdk synth

# Show differences between deployed and local
cdk diff

# Destroy all stacks (WARNING: deletes resources)
cdk destroy --all

# Watch mode (auto-deploy on changes)
cdk watch
```

## Outputs

After deployment, CDK will output:

- **ApiUrl**: API Gateway endpoint URL
- **AssetsBucket**: S3 bucket name for static assets
- **DistributionDomain**: CloudFront distribution domain
- **DistributionId**: CloudFront distribution ID

## Environment Variables

The application uses the following environment variables (automatically configured by CDK):

- `DYNAMODB_TABLE_NAME`: DynamoDB events table name
- `ASSETS_BUCKET`: S3 bucket for static assets and groups
- `ENVIRONMENT`: Deployment environment (prod/dev/staging)

## Monitoring

CloudWatch Logs groups created:
- `/aws/lambda/DCTechEvents-EventCollection-{env}`
- `/aws/lambda/DCTechEvents-ManualRefresh-{env}`
- `/aws/lambda/{chalice-app-name}`

CloudWatch Metrics to monitor:
- Lambda: Invocations, Duration, Errors, Throttles
- DynamoDB: ConsumedReadCapacityUnits, ConsumedWriteCapacityUnits
- API Gateway: Count, Latency, 4XXError, 5XXError
- CloudFront: Requests, BytesDownloaded, ErrorRate

## Cost Optimization

The infrastructure uses:
- **DynamoDB**: On-demand pricing (pay per request)
- **Lambda**: Pay per invocation and duration
- **API Gateway**: Pay per request
- **CloudFront**: Pay per request and data transfer
- **S3**: Pay per storage and requests

Expected costs for low-moderate traffic: ~$10-15/month

## Cleanup

To delete all resources:

```bash
cdk destroy --all
```

**Note**: The DynamoDB table has `RETAIN` removal policy for data protection.
To fully delete, manually delete the table from AWS Console after running destroy.

## Troubleshooting

### CDK Bootstrap Issues

If you get bootstrap errors:
```bash
cdk bootstrap aws://ACCOUNT-ID/us-east-1
```

### Chalice Deployment Fails

Ensure the Chalice app exists at `../chalice-app/`:
```bash
cd ..
chalice new-project chalice-app
```

### Permission Errors

Ensure your AWS credentials have sufficient permissions:
- CloudFormation: Full access
- Lambda: Full access
- DynamoDB: Full access
- S3: Full access
- IAM: Role creation
- API Gateway: Full access
- CloudFront: Full access

## Directory Structure

```
infrastructure/
├── app.py                    # CDK app entry point
├── cdk.json                  # CDK configuration
├── requirements.txt          # Python dependencies
├── README.md                 # This file
└── stacks/
    ├── __init__.py
    ├── database_stack.py     # DynamoDB table
    ├── application_stack.py  # Chalice API
    ├── scheduler_stack.py    # Event collection Lambda
    └── distribution_stack.py # CloudFront CDN
```
