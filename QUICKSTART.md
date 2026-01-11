# Quick Start Guide - DC Tech Events Serverless

Get the serverless DC Tech Events application running in 15 minutes.

## Prerequisites

```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Install Node.js (for CDK)
# Visit: https://nodejs.org/

# Install Python 3.11+
python3 --version

# Install AWS CDK
npm install -g aws-cdk

# Verify installations
aws --version
node --version
python3 --version
cdk --version
```

## Setup AWS Credentials

```bash
# Configure AWS CLI
aws configure
# Enter:
#   AWS Access Key ID: YOUR_ACCESS_KEY
#   AWS Secret Access Key: YOUR_SECRET_KEY
#   Default region: us-east-1
#   Default output format: json

# Verify
aws sts get-caller-identity
```

## Deploy in 5 Steps

### Step 1: Clone Repository

```bash
git clone https://github.com/rosskarchner/dctech.events.git
cd dctech.events
```

### Step 2: Install Dependencies

```bash
# Quick install using Make
make install

# Or manual install
cd infrastructure
pip install -r requirements.txt
cd ../chalice-app
pip install -r requirements.txt
cd ..
```

### Step 3: Bootstrap CDK

```bash
# Set environment variables
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export CDK_DEFAULT_REGION=us-east-1

# Bootstrap (first time only)
make bootstrap

# Or manually
cd infrastructure && cdk bootstrap
```

### Step 4: Deploy All Stacks

```bash
# Deploy everything
make deploy

# Or manually
cd infrastructure
cdk deploy --all --require-approval never
```

**Wait**: 10-15 minutes for CloudFormation stacks to deploy.

### Step 5: Load Initial Data

```bash
# Trigger event collection
make refresh

# Or manually
FUNCTION_NAME=$(aws lambda list-functions --query "Functions[?starts_with(FunctionName, 'DCTechEvents-EventCollection')].FunctionName" --output text)
aws lambda invoke --function-name $FUNCTION_NAME --invocation-type Event /tmp/response.json

# Wait 5-10 minutes for events to populate
```

## Verify Deployment

### Check Deployment Status

```bash
make status
```

**Expected output:**
```
DC Tech Events - Deployment Status
====================================

Environment: prod
Region: us-east-1

CloudFormation Stacks:
---------------------
DCTechEvents-Database-prod       CREATE_COMPLETE
DCTechEvents-Application-prod    CREATE_COMPLETE
DCTechEvents-Scheduler-prod      CREATE_COMPLETE
DCTechEvents-Distribution-prod   CREATE_COMPLETE

API Endpoint:
------------
API Gateway: https://abcd1234.execute-api.us-east-1.amazonaws.com/api
CloudFront: https://d111111abcdef8.cloudfront.net

DynamoDB Table:
--------------
Table: DCTechEvents-Events-prod
Event count: 150
```

### Test API Endpoints

```bash
# Get your CloudFront URL
CLOUDFRONT_URL=$(aws cloudformation describe-stacks \
  --stack-name DCTechEvents-Distribution-prod \
  --query "Stacks[0].Outputs[?OutputKey=='DistributionDomain'].OutputValue" \
  --output text)

echo "Your API: https://$CLOUDFRONT_URL"

# Test health check
curl https://$CLOUDFRONT_URL/health

# Test events API
curl https://$CLOUDFRONT_URL/api/events/upcoming

# Test groups API
curl https://$CLOUDFRONT_URL/api/groups
```

**Expected output** (health check):
```json
{
  "status": "healthy",
  "timestamp": "2026-01-11T12:00:00-05:00",
  "environment": "prod"
}
```

### Test with Make

```bash
# Automated API testing
make test-api
```

## Common Operations

### View Logs

```bash
# Event collection Lambda logs
make logs-collection

# API Lambda logs
make logs-api
```

### Manually Refresh Events

```bash
# Trigger calendar refresh
make refresh

# Watch logs
make logs-collection
```

### Check Event Count

```bash
# Count events in DynamoDB
make db-count

# Expected: 100-200 events
```

### Invalidate CloudFront Cache

```bash
# After making changes
make invalidate-cache
```

## Local Development

### Run Chalice App Locally

```bash
# Set environment variables
export DYNAMODB_TABLE_NAME=DCTechEvents-Events-prod
export ASSETS_BUCKET=dctechevents-assets-prod
export AWS_DEFAULT_REGION=us-east-1

# Run local server
cd chalice-app
chalice local --port 8000

# Test
curl http://localhost:8000/health
```

### Update and Redeploy

```bash
# Make changes to Chalice app
# Edit chalice-app/app.py or chalice-app/chalicelib/*.py

# Redeploy
make deploy-app

# Or
cd infrastructure
cdk deploy DCTechEvents-Application-prod
```

## Troubleshooting

### Issue: CDK Bootstrap Fails

```bash
# Solution: Re-bootstrap with force
cd infrastructure
cdk bootstrap --force
```

### Issue: No Events in DynamoDB

```bash
# Check if event collection ran
make logs-collection

# Manually trigger
make refresh

# Wait 5 minutes and check count
make db-count
```

### Issue: API Returns Empty Data

```bash
# Verify DynamoDB has events
make db-count

# Check if events are in the future
aws dynamodb query \
  --table-name DCTechEvents-Events-prod \
  --index-name DateIndex \
  --key-condition-expression "state = :state AND start_datetime >= :start" \
  --expression-attribute-values '{":state":{"S":"DC"},":start":{"S":"2026-01-01"}}'
```

### Issue: CloudFront Serving 502 Errors

```bash
# Check API Gateway health
API_URL=$(aws cloudformation describe-stacks \
  --stack-name DCTechEvents-Application-prod \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
  --output text)

curl $API_URL/health

# If API is down, check Lambda logs
make logs-api
```

### Issue: Lambda Timeout

```bash
# Increase timeout (edit infrastructure/stacks/scheduler_stack.py)
timeout=Duration.minutes(15)  # Increase from default

# Redeploy
make deploy-scheduler
```

## Cost Monitoring

### Check Current Month Costs

```bash
# AWS Cost Explorer (via Console)
# Or use CLI
aws ce get-cost-and-usage \
  --time-period Start=2026-01-01,End=2026-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --filter file://filter.json

# Expected: $10-15/month
```

### Set Up Billing Alerts

1. Go to AWS Console → Billing → Budgets
2. Create Budget
3. Set threshold: $20/month
4. Configure email alerts

## Next Steps

### 1. Configure Custom Domain (Optional)

```bash
# Request ACM certificate
aws acm request-certificate \
  --domain-name dctech.events \
  --validation-method DNS \
  --region us-east-1

# Validate via DNS
# Update infrastructure/stacks/distribution_stack.py
# Add certificate ARN

# Redeploy
make deploy-cdn

# Update DNS
# dctech.events CNAME d111111abcdef8.cloudfront.net
```

### 2. Set Up Monitoring

```bash
# Create CloudWatch Dashboard
# Add widgets for:
# - Lambda invocations
# - DynamoDB read/write capacity
# - API Gateway latency
# - CloudFront requests
```

### 3. Build Frontend

```bash
# Create React app
npx create-react-app frontend
cd frontend

# Install dependencies
npm install axios date-fns

# Configure API endpoint
# REACT_APP_API_URL=https://your-cloudfront-url.cloudfront.net

# Build and deploy to S3
npm run build
aws s3 sync build/ s3://your-frontend-bucket/
```

### 4. Enable CI/CD

Add GitHub Actions workflow:

```yaml
# .github/workflows/deploy-serverless.yml
name: Deploy Serverless
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - uses: actions/setup-node@v3
      - run: npm install -g aws-cdk
      - run: make deploy
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

## Useful Commands

### Make Commands

```bash
make help              # Show all available commands
make install           # Install all dependencies
make bootstrap         # Bootstrap CDK
make deploy            # Deploy all stacks
make deploy-app        # Deploy Chalice app only
make refresh           # Trigger event collection
make logs-api          # View API logs
make logs-collection   # View event collection logs
make status            # Show deployment status
make test-api          # Test API endpoints
make invalidate-cache  # Invalidate CloudFront cache
make db-count          # Count events in DynamoDB
make clean             # Clean build artifacts
make destroy           # Destroy all stacks (WARNING!)
```

### CDK Commands

```bash
cd infrastructure

cdk list               # List all stacks
cdk synth              # Synthesize CloudFormation
cdk diff               # Show differences
cdk deploy --all       # Deploy all stacks
cdk destroy --all      # Destroy all stacks
```

### AWS CLI Commands

```bash
# List Lambda functions
aws lambda list-functions

# List DynamoDB tables
aws dynamodb list-tables

# Describe CloudFormation stack
aws cloudformation describe-stacks --stack-name DCTechEvents-Database-prod

# List S3 buckets
aws s3 ls

# View CloudWatch logs
aws logs tail /aws/lambda/DCTechEvents-EventCollection-prod --follow
```

## Documentation

- **Architecture**: See `ARCHITECTURE.md`
- **Deployment**: See `DEPLOYMENT.md`
- **Migration**: See `MIGRATION.md`
- **Serverless Guide**: See `README-SERVERLESS.md`

## Support

- **GitHub Issues**: https://github.com/rosskarchner/dctech.events/issues
- **AWS Documentation**: https://docs.aws.amazon.com/
- **Chalice Documentation**: https://aws.github.io/chalice/
- **CDK Documentation**: https://docs.aws.amazon.com/cdk/

## Summary

You now have:

✅ **DynamoDB** table storing events
✅ **Lambda** functions for API and event collection
✅ **API Gateway** REST API
✅ **CloudFront** CDN for caching
✅ **S3** bucket for groups and static assets
✅ **EventBridge** scheduled daily refresh

**API Endpoint**: `https://YOUR_CLOUDFRONT_URL`

**Test**: `curl https://YOUR_CLOUDFRONT_URL/health`

Happy coding! 🚀
