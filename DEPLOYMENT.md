# DC Tech Events - Deployment Guide

Complete guide for deploying the serverless DC Tech Events application on AWS.

## Architecture Overview

The new architecture uses:

- **DynamoDB** - Event storage (replacing YAML files)
- **AWS Lambda** - Serverless compute for API and event collection
- **API Gateway** - REST API endpoints
- **CloudFront** - Global CDN for caching and performance
- **S3** - Static assets and group definitions
- **EventBridge** - Scheduled calendar refresh (daily at 2 AM UTC)
- **AWS CDK** - Infrastructure as Code (Python)
- **Chalice** - Serverless Python framework

## Prerequisites

### Required Tools

```bash
# Python 3.11+
python3 --version

# Node.js 18+ (for AWS CDK)
node --version

# AWS CLI configured
aws --version
aws configure list

# AWS CDK CLI
npm install -g aws-cdk

# Python virtual environment
python3 -m pip install virtualenv
```

### AWS Account Setup

1. **AWS Account** with appropriate permissions
2. **IAM User** with permissions for:
   - CloudFormation
   - Lambda
   - DynamoDB
   - S3
   - API Gateway
   - CloudFront
   - IAM (role creation)
   - EventBridge

3. **AWS Credentials** configured locally:
```bash
aws configure
# Enter: Access Key ID, Secret Access Key, Region (us-east-1), Output format (json)
```

## Quick Start

### 1. Bootstrap AWS CDK (First Time Only)

```bash
cd infrastructure
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export CDK_DEFAULT_REGION=us-east-1

cdk bootstrap aws://$CDK_DEFAULT_ACCOUNT/$CDK_DEFAULT_REGION
```

### 2. Deploy Infrastructure

```bash
# Install CDK dependencies
cd infrastructure
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Deploy all stacks
cdk deploy --all --require-approval never

# Or deploy individually
cdk deploy DCTechEvents-Database-prod
cdk deploy DCTechEvents-Application-prod
cdk deploy DCTechEvents-Scheduler-prod
cdk deploy DCTechEvents-Distribution-prod
```

### 3. Initial Data Load

After deployment, trigger the calendar refresh Lambda to populate DynamoDB:

```bash
# Get the Lambda function name
FUNCTION_NAME=$(aws lambda list-functions --query "Functions[?starts_with(FunctionName, 'DCTechEvents-EventCollection')].FunctionName" --output text)

# Invoke the function
aws lambda invoke --function-name $FUNCTION_NAME --invocation-type Event /dev/null

# Check logs
aws logs tail /aws/lambda/$FUNCTION_NAME --follow
```

### 4. Get API Endpoints

```bash
# Get API Gateway URL
aws cloudformation describe-stacks \
  --stack-name DCTechEvents-Application-prod \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
  --output text

# Get CloudFront distribution URL
aws cloudformation describe-stacks \
  --stack-name DCTechEvents-Distribution-prod \
  --query "Stacks[0].Outputs[?OutputKey=='DistributionDomain'].OutputValue" \
  --output text
```

### 5. Test the API

```bash
# Set CloudFront URL
export CLOUDFRONT_URL=$(aws cloudformation describe-stacks \
  --stack-name DCTechEvents-Distribution-prod \
  --query "Stacks[0].Outputs[?OutputKey=='DistributionDomain'].OutputValue" \
  --output text)

# Test endpoints
curl https://$CLOUDFRONT_URL/health
curl https://$CLOUDFRONT_URL/api/events/upcoming
curl https://$CLOUDFRONT_URL/api/groups
```

## Detailed Deployment Steps

### Step 1: Prepare the Environment

```bash
# Clone the repository
git clone https://github.com/rosskarchner/dctech.events.git
cd dctech.events

# Set AWS environment variables
export AWS_PROFILE=default  # or your profile name
export AWS_REGION=us-east-1
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export CDK_DEFAULT_REGION=$AWS_REGION
```

### Step 2: Deploy Database Stack

```bash
cd infrastructure
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Preview changes
cdk diff DCTechEvents-Database-prod

# Deploy
cdk deploy DCTechEvents-Database-prod
```

This creates:
- DynamoDB Events table
- Global Secondary Indexes (DateIndex, GroupIndex, LocationTypeIndex)
- TTL configuration

### Step 3: Deploy Application Stack

```bash
# Deploy Chalice app + S3 bucket
cdk deploy DCTechEvents-Application-prod
```

This creates:
- S3 bucket for static assets and groups
- Chalice Lambda function
- API Gateway REST API
- IAM roles and permissions

**Note**: The first deploy uploads group YAML files from `_groups/` to S3.

### Step 4: Deploy Scheduler Stack

```bash
# Deploy event collection Lambda
cdk deploy DCTechEvents-Scheduler-prod
```

This creates:
- Event collection Lambda function
- EventBridge scheduled rule (daily at 2 AM UTC)
- Manual refresh Lambda (for testing)

### Step 5: Deploy CloudFront Distribution

```bash
# Deploy CDN
cdk deploy DCTechEvents-Distribution-prod
```

This creates:
- CloudFront distribution
- Cache policies
- Origin configuration pointing to API Gateway

**Note**: CloudFront distribution takes 10-15 minutes to fully deploy.

### Step 6: Initial Data Population

```bash
# Trigger calendar refresh
FUNCTION_NAME=$(aws lambda list-functions --query "Functions[?starts_with(FunctionName, 'DCTechEvents-EventCollection')].FunctionName" --output text)

aws lambda invoke \
  --function-name $FUNCTION_NAME \
  --invocation-type Event \
  /tmp/response.json

# Wait a few minutes, then check DynamoDB
aws dynamodb scan \
  --table-name DCTechEvents-Events-prod \
  --max-items 5
```

### Step 7: Configure Custom Domain (Optional)

To use a custom domain like `dctech.events`:

1. **Request ACM Certificate** (in us-east-1 for CloudFront):
```bash
aws acm request-certificate \
  --domain-name dctech.events \
  --validation-method DNS \
  --region us-east-1
```

2. **Validate Certificate** via DNS

3. **Update CDK** - Add to `distribution_stack.py`:
```python
from aws_cdk import aws_certificatemanager as acm

# Get certificate ARN
certificate = acm.Certificate.from_certificate_arn(
    self, 'Certificate',
    certificate_arn='arn:aws:acm:us-east-1:ACCOUNT:certificate/CERT_ID'
)

# Add to distribution
self.distribution = cloudfront.Distribution(
    self,
    "Distribution",
    domain_names=['dctech.events'],
    certificate=certificate,
    # ... other config
)
```

4. **Update DNS** - Point `dctech.events` CNAME to CloudFront distribution

5. **Redeploy**:
```bash
cdk deploy DCTechEvents-Distribution-prod
```

## Environment-Specific Deployments

### Development Environment

```bash
# Deploy to dev
cdk deploy --all --context environment=dev

# This creates:
# - DCTechEvents-Database-dev
# - DCTechEvents-Application-dev
# - DCTechEvents-Scheduler-dev
# - DCTechEvents-Distribution-dev
```

### Staging Environment

```bash
cdk deploy --all --context environment=staging
```

### Production Environment

```bash
cdk deploy --all --context environment=prod
```

## Updating the Application

### Update Chalice API Code

```bash
# Make changes to chalice-app/

# Redeploy
cd infrastructure
cdk deploy DCTechEvents-Application-prod
```

### Update Event Collection Lambda

```bash
# Make changes to lambda/event-collection/

# Redeploy
cd infrastructure
cdk deploy DCTechEvents-Scheduler-prod
```

### Update Group Definitions

```bash
# Make changes to _groups/*.yaml

# Redeploy to sync to S3
cd infrastructure
cdk deploy DCTechEvents-Application-prod
```

### Update Infrastructure

```bash
# Make changes to infrastructure/stacks/*.py

# Preview changes
cdk diff

# Deploy
cdk deploy --all
```

## Monitoring and Logs

### View Lambda Logs

```bash
# Event collection Lambda
aws logs tail /aws/lambda/DCTechEvents-EventCollection-prod --follow

# Chalice API Lambda
CHALICE_FUNCTION=$(aws lambda list-functions --query "Functions[?contains(FunctionName, 'dctech-events')].FunctionName" --output text)
aws logs tail /aws/lambda/$CHALICE_FUNCTION --follow
```

### View API Gateway Logs

```bash
# Enable execution logs in API Gateway console
# Then view in CloudWatch Logs
```

### Monitor DynamoDB

```bash
# Get table statistics
aws dynamodb describe-table --table-name DCTechEvents-Events-prod

# Scan for recent events
aws dynamodb query \
  --table-name DCTechEvents-Events-prod \
  --index-name DateIndex \
  --key-condition-expression "state = :state AND start_datetime > :start" \
  --expression-attribute-values '{":state":{"S":"DC"},":start":{"S":"2026-01-01"}}' \
  --max-items 10
```

### CloudFront Cache Statistics

```bash
# View in AWS Console: CloudFront > Distributions > Monitoring
# Or use CloudWatch Metrics
```

## Troubleshooting

### CDK Bootstrap Errors

```bash
# Re-bootstrap
cdk bootstrap aws://$CDK_DEFAULT_ACCOUNT/$CDK_DEFAULT_REGION --force
```

### Chalice Deployment Fails

```bash
# Check Chalice app locally
cd chalice-app
chalice local

# Test
curl http://localhost:8000/health
```

### Lambda Timeout

If event collection times out (max 15 minutes):

1. **Increase timeout** in `scheduler_stack.py`:
```python
timeout=Duration.minutes(15),  # Increase if needed
```

2. **Reduce date range** - Process fewer days of events
3. **Batch processing** - Split groups across multiple invocations

### DynamoDB Throttling

If experiencing throttling:

1. **Check CloudWatch metrics** for ThrottledRequests
2. **Increase provisioned capacity** (if using provisioned mode)
3. **Use on-demand mode** (current default)

### CloudFront Errors

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

## Cleanup / Destroy

To remove all resources:

```bash
cd infrastructure

# Destroy all stacks
cdk destroy --all

# Note: DynamoDB table has RETAIN policy
# Manually delete from AWS Console if needed
```

**Warning**: This will delete all data. Backup DynamoDB table first if needed:

```bash
# Export to S3
aws dynamodb export-table-to-point-in-time \
  --table-arn arn:aws:dynamodb:REGION:ACCOUNT:table/DCTechEvents-Events-prod \
  --s3-bucket my-backup-bucket \
  --s3-prefix backup/events/
```

## Cost Estimation

For low-moderate traffic (100K requests/month):

| Service | Cost |
|---------|------|
| DynamoDB | $0.25/month (on-demand) |
| Lambda (API) | $0.20/month |
| Lambda (Event Collection) | $0.00 (free tier) |
| API Gateway | $0.35/month |
| CloudFront | $8.60/month |
| S3 | $0.50/month |
| **Total** | **~$10-15/month** |

Free tier eligible for first 12 months.

## Security Best Practices

1. **Use IAM roles** - Never hardcode credentials
2. **Enable encryption** - DynamoDB encryption at rest (enabled by default)
3. **API authentication** - Consider API keys for external access
4. **CloudFront SSL** - HTTPS only (configured)
5. **VPC endpoints** - For Lambda to DynamoDB (optional, for extra security)
6. **Secrets Manager** - For API keys (if using OAuth)

## Next Steps

- [ ] Configure custom domain
- [ ] Set up monitoring alarms
- [ ] Implement API rate limiting
- [ ] Add frontend (React/Vue)
- [ ] Implement event submission API
- [ ] Set up CI/CD pipeline
- [ ] Configure backups

## Support

For issues or questions:
- GitHub Issues: https://github.com/rosskarchner/dctech.events/issues
- AWS Documentation: https://docs.aws.amazon.com/
