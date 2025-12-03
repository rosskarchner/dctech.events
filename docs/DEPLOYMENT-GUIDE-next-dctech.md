# Deployment Guide: next.dctech.events

This guide walks through deploying the new next.dctech.events site based on the implementation plan.

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI configured
- Node.js 20.x installed
- CDK CLI installed (`npm install -g aws-cdk`)
- GitHub Personal Access Token (for syncing)

## Step 1: Install Dependencies

```bash
# Install CDK dependencies
cd infrastructure
npm install

# Install Lambda API dependencies
cd lambda/api
npm install
cd ../..

# Install Python dependencies for refresh Lambda
cd infrastructure/lambda/refresh
pip install -r requirements.txt -t .
cd ../../..
```

## Step 2: Configure GitHub Token

Create a GitHub Personal Access Token with `repo` scope and store it in AWS Secrets Manager:

```bash
aws secretsmanager create-secret \
  --name dctech-events/github-token \
  --secret-string "ghp_YOUR_GITHUB_TOKEN" \
  --region us-east-1
```

## Step 3: Bootstrap CDK (if not already done)

```bash
cd infrastructure
cdk bootstrap aws://ACCOUNT-ID/us-east-1
```

## Step 4: Deploy the Stack

The stack MUST be deployed to us-east-1 (CloudFront requirement):

```bash
cd infrastructure
cdk deploy --region us-east-1
```

This will:
- Create ACM certificate for next.dctech.events
- Create CloudFront distribution
- Deploy API Lambda with Handlebars templates
- Deploy refresh Lambda for iCal sync
- Create EventBridge rule for 4-hour refresh
- Set up Route 53 DNS records

## Step 5: Upload Static Assets to S3

After deployment, upload CSS and JS files to the S3 bucket:

```bash
# Get bucket name from CDK output
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name InfrastructureStack \
  --query 'Stacks[0].Outputs[?OutputKey==`WebsiteBucketName`].OutputValue' \
  --output text \
  --region us-east-1)

# Upload static assets
aws s3 sync infrastructure/frontend/static/ s3://$BUCKET_NAME/static/ \
  --region us-east-1
```

## Step 6: Verify Certificate Validation

DNS validation can take 20-30 minutes. Check certificate status:

```bash
aws acm list-certificates --region us-east-1
```

## Step 7: Test the Refresh Lambda

Manually trigger the refresh Lambda to populate initial data:

```bash
aws lambda invoke \
  --function-name InfrastructureStack-RefreshFunction-XXXXX \
  --region us-east-1 \
  response.json

cat response.json
```

Check CloudWatch Logs to verify:
- Groups synced from GitHub
- Events synced from GitHub
- iCal feeds fetched successfully

## Step 8: Verify next.dctech.events

Once DNS propagates (usually 5-15 minutes), visit:

- https://next.dctech.events/
- https://next.dctech.events/groups/
- https://next.dctech.events/locations/
- https://next.dctech.events/newsletter.html
- https://next.dctech.events/sitemap.xml

## Step 9: Test Authentication

Try submitting an event or group to verify Cognito authentication:

- Visit https://next.dctech.events/submit/
- Should redirect to Cognito login
- Sign up for new account
- Verify event submission works

## Troubleshooting

### Certificate Not Validating

Check Route 53 for validation CNAME records:

```bash
aws route53 list-resource-record-sets \
  --hosted-zone-id YOUR_ZONE_ID \
  --query "ResourceRecordSets[?Type=='CNAME']"
```

### Lambda Errors

Check CloudWatch Logs:

```bash
aws logs tail /aws/lambda/InfrastructureStack-ApiFunction-XXXXX --follow --region us-east-1
aws logs tail /aws/lambda/InfrastructureStack-RefreshFunction-XXXXX --follow --region us-east-1
```

### No Events Showing

1. Check if refresh Lambda ran successfully
2. Verify DynamoDB tables have data:
   ```bash
   aws dynamodb scan --table-name organize-events --max-items 10 --region us-east-1
   aws dynamodb scan --table-name organize-groups --max-items 10 --region us-east-1
   ```

### CloudFront Not Serving Content

- Wait 10-15 minutes for distribution to deploy
- Check distribution status in AWS Console
- Verify origin settings point to correct API Gateway

## Monitoring

### CloudWatch Alarms

The stack includes alarms for:
- API Lambda errors
- Refresh Lambda errors
- DynamoDB throttling

### Metrics to Watch

- Lambda invocation count
- Lambda error count
- CloudFront cache hit ratio
- DynamoDB read/write units

## Ongoing Maintenance

### Refresh Schedule

The refresh Lambda runs every 4 hours automatically to:
1. Sync groups from GitHub `_groups/*.yaml`
2. Sync events from GitHub `_single_events/*.yaml`
3. Fetch iCal feeds for all active groups

### Manual Refresh

To manually trigger a refresh:

```bash
aws lambda invoke \
  --function-name InfrastructureStack-RefreshFunction-XXXXX \
  --region us-east-1 \
  response.json
```

### Updating Templates

After updating Handlebars templates:

```bash
cd infrastructure
cdk deploy --region us-east-1
```

The Lambda layer will be updated with new templates.

## Rollback

To roll back the deployment:

```bash
cd infrastructure
cdk destroy --region us-east-1
```

Note: This will NOT affect organize.dctech.events or the existing dctech.events GitHub Pages site.

## Next Steps

Once next.dctech.events is stable:
1. Monitor for 1-2 weeks
2. Gather user feedback
3. Plan migration of dctech.events DNS to point to new infrastructure
4. Archive static site generation scripts

## Support

- Check CloudWatch Logs for errors
- Review CDK stack events in CloudFormation console
- Verify Route 53 DNS records
- Check API Gateway logs
