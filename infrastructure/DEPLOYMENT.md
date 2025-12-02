# Deployment Guide for Organize DC Tech Events

This guide provides step-by-step instructions for deploying the organize.dctech.events infrastructure.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Setup](#initial-setup)
3. [Deploy Infrastructure](#deploy-infrastructure)
4. [Configure and Deploy Frontend](#configure-and-deploy-frontend)
5. [Configure Domain (Optional)](#configure-domain-optional)
6. [Verify Deployment](#verify-deployment)
7. [Update Main Site Integration](#update-main-site-integration)

## Prerequisites

### Required Tools

- **AWS CLI**: [Installation guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- **Node.js 18+**: [Download](https://nodejs.org/)
- **AWS CDK CLI**: Install with `npm install -g aws-cdk`

### AWS Account Setup

1. Create an AWS account if you don't have one
2. Configure AWS CLI credentials:
   ```bash
   aws configure
   ```
3. Note your AWS account ID and preferred region

### Optional: Custom Domain

If using a custom domain:
- Domain registered and hosted in Route53 (or external DNS provider)
- ACM certificate in **us-east-1** region (required for CloudFront)

## Initial Setup

### 1. Clone Repository

```bash
cd dctech.events/infrastructure
```

### 2. Install CDK Dependencies

```bash
npm install
```

### 3. Install Lambda Dependencies

```bash
# API Lambda
cd lambda/api
npm install
cd ../..

# Export Lambda
cd lambda/export
npm install
cd ../..
```

### 4. Bootstrap CDK (First Time Only)

```bash
npx cdk bootstrap aws://ACCOUNT-ID/REGION
```

Replace `ACCOUNT-ID` with your AWS account ID and `REGION` with your preferred region (e.g., `us-east-1`).

## Deploy Infrastructure

### 1. Review Stack Configuration

Edit `bin/infrastructure.ts` if you want to customize the stack name or configuration:

```typescript
#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib/core';
import { InfrastructureStack } from '../lib/infrastructure-stack';

const app = new cdk.App();
new InfrastructureStack(app, 'OrganizeDCTechStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
  // Optional: Add custom domain configuration
  // domainName: 'organize.dctech.events',
  // certificateArn: 'arn:aws:acm:us-east-1:ACCOUNT:certificate/CERT_ID',
});
```

### 2. Synthesize CloudFormation Template (Optional)

Review what will be deployed:

```bash
npx cdk synth
```

### 3. Deploy the Stack

```bash
npx cdk deploy
```

You'll be prompted to approve IAM changes. Type `y` and press Enter.

### 4. Save the Outputs

The deployment will output important values. **Save these!**

```
Outputs:
OrganizeDCTechStack.UserPoolId = us-east-1_XXXXXXXXX
OrganizeDCTechStack.UserPoolClientId = 1234567890abcdefghij
OrganizeDCTechStack.UserPoolDomain = organize-dctech-events
OrganizeDCTechStack.ApiUrl = https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod/
OrganizeDCTechStack.CloudFrontUrl = d1234567890abc.cloudfront.net
OrganizeDCTechStack.WebsiteBucketName = organize-dctech-events
OrganizeDCTechStack.GroupsYamlUrl = https://d1234567890abc.cloudfront.net/groups.yaml
OrganizeDCTechStack.EventsYamlUrl = https://d1234567890abc.cloudfront.net/events.yaml
```

## Configure and Deploy Frontend

The frontend uses HTMX for dynamic interactions and vanilla JavaScript for authentication. No build step required!

### 1. Configure Frontend

Edit `frontend/public/js/config.js` with your CDK stack outputs:

```javascript
window.CONFIG = {
    userPoolId: 'us-east-1_XXXXXXXXX',          // From UserPoolId output
    userPoolClientId: '1234567890abcdefghij',    // From UserPoolClientId output
    region: 'us-east-1',
    apiUrl: 'https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod/'  // From ApiUrl output
};
```

Replace the values with your CDK stack outputs.

### 2. Deploy to S3

No build step needed! Just sync the public directory directly to S3:

```bash
cd frontend/public
aws s3 sync . s3://organize-dctech-events --delete
```

### 3. Invalidate CloudFront Cache

Get your CloudFront distribution ID:

```bash
aws cloudfront list-distributions --query "DistributionList.Items[?Comment=='organize.dctech.events'].Id" --output text
```

Then invalidate the cache:

```bash
aws cloudfront create-invalidation \
  --distribution-id YOUR_DISTRIBUTION_ID \
  --paths "/*"
```

## Configure Domain (Optional)

### Option 1: Using Route53

1. **Create ACM Certificate** (in us-east-1):
   ```bash
   aws acm request-certificate \
     --domain-name organize.dctech.events \
     --validation-method DNS \
     --region us-east-1
   ```

2. **Validate Certificate**:
   - Add the DNS records provided by ACM to your Route53 hosted zone
   - Wait for validation (usually 5-30 minutes)

3. **Get Certificate ARN**:
   ```bash
   aws acm list-certificates --region us-east-1
   ```

4. **Update CDK Stack**:
   Edit `bin/infrastructure.ts`:
   ```typescript
   new InfrastructureStack(app, 'OrganizeDCTechStack', {
     env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: 'us-east-1' },
     domainName: 'organize.dctech.events',
     certificateArn: 'arn:aws:acm:us-east-1:ACCOUNT:certificate/CERT_ID',
     hostedZoneId: 'YOUR_HOSTED_ZONE_ID',
   });
   ```

5. **Redeploy**:
   ```bash
   npx cdk deploy
   ```

6. **Add DNS Record**:
   - Get the CloudFront distribution domain from outputs
   - Create a CNAME or ALIAS record pointing organize.dctech.events to the distribution

### Option 2: Using External DNS Provider

1. Follow steps 1-5 above, omitting `hostedZoneId`
2. After redeployment, get the CloudFront domain
3. In your DNS provider, create a CNAME record:
   - Name: `organize` (or `organize.dctech`)
   - Value: CloudFront domain (e.g., `d1234567890abc.cloudfront.net`)
   - TTL: 300 (5 minutes)

## Verify Deployment

### 1. Test Frontend

Visit your CloudFront URL (or custom domain):
```
https://YOUR_CLOUDFRONT_DOMAIN.cloudfront.net
```

You should see the Organize DC Tech Events homepage.

### 2. Test Authentication

1. Click "Sign Up" and create an account
2. Check your email for verification code
3. Sign in with your credentials

### 3. Test API

Create a test group:
1. After signing in, click "Create Group"
2. Fill in the form and submit
3. Verify the group appears in the "Groups" list

### 4. Test Exports

Wait 5 minutes for the first export to run, then check:

```bash
curl https://YOUR_CLOUDFRONT_DOMAIN.cloudfront.net/groups.yaml
curl https://YOUR_CLOUDFRONT_DOMAIN.cloudfront.net/events.yaml
```

You should see YAML output.

### 5. Monitor Logs

Check Lambda logs for any errors:

```bash
# Export function logs
aws logs tail /aws/lambda/OrganizeDCTechStack-ExportFunction --follow

# API function logs
aws logs tail /aws/lambda/OrganizeDCTechStack-ApiFunction --follow
```

## Update Main Site Integration

### 1. Verify Config

Check that `config.yaml` in the main dctech.events repository contains:

```yaml
organize_groups_url: "https://organize.dctech.events/groups.yaml"
organize_events_url: "https://organize.dctech.events/events.yaml"
```

Or use your CloudFront URL if not using a custom domain.

### 2. Test Main Site Build

```bash
cd /home/user/dctech.events
python3 generate_month_data.py
```

You should see output like:
```
Fetching groups from https://organize.dctech.events/groups.yaml...
Added group from organize.dctech.events: Test Group
Fetching events from https://organize.dctech.events/events.yaml...
Added event from organize.dctech.events: Test Event
```

### 3. Rebuild Main Site

Follow your normal deployment process for dctech.events to publish the updated calendar with data from organize.dctech.events.

## Troubleshooting

### CloudFormation Stack Failed

1. Check the CloudFormation console for detailed error messages
2. Common issues:
   - Resource limits (DynamoDB tables, Lambda functions)
   - IAM permission issues
   - Naming conflicts

Solution: Delete the stack and retry:
```bash
npx cdk destroy
npx cdk deploy
```

### Frontend Shows CORS Errors

1. Verify API URL in frontend config matches CDK output
2. Check API Gateway CORS settings
3. Ensure Cognito callback URLs include your domain

### Export Lambda Not Running

1. Check EventBridge rule is enabled:
   ```bash
   aws events list-rules --name-prefix OrganizeDCTech
   ```

2. Check Lambda permissions:
   ```bash
   aws lambda get-policy --function-name OrganizeDCTechStack-ExportFunction
   ```

3. Manually invoke:
   ```bash
   aws lambda invoke --function-name OrganizeDCTechStack-ExportFunction output.json
   ```

### Users Can't Sign Up

1. Check Cognito email settings (may be in SES sandbox)
2. Verify email verification is configured
3. Check CloudWatch Logs for Cognito errors

## Updating the Deployment

### Update Lambda Code

```bash
cd lambda/api  # or lambda/export
# Make your changes
cd ../..
npx cdk deploy
```

### Update Frontend

```bash
cd frontend/public
# Make your changes to HTML, CSS, or JS files
aws s3 sync . s3://organize-dctech-events --delete
aws cloudfront create-invalidation --distribution-id YOUR_DIST_ID --paths "/*"
```

### Update Infrastructure

```bash
# Edit lib/infrastructure-stack.ts
npx cdk diff  # Review changes
npx cdk deploy
```

## Clean Up

To remove all resources:

```bash
# Delete S3 bucket contents first
aws s3 rm s3://organize-dctech-events --recursive

# Destroy stack
npx cdk destroy
```

Note: DynamoDB tables with `RETAIN` policy will not be deleted. Remove manually if needed:

```bash
aws dynamodb delete-table --table-name organize-users
aws dynamodb delete-table --table-name organize-groups
aws dynamodb delete-table --table-name organize-group-members
aws dynamodb delete-table --table-name organize-events
aws dynamodb delete-table --table-name organize-rsvps
aws dynamodb delete-table --table-name organize-messages
```

## Next Steps

- Set up CloudWatch alarms for Lambda errors
- Configure custom email domain in SES (to exit sandbox)
- Set up CloudWatch Dashboards for monitoring
- Configure backup retention policies
- Set up CI/CD pipeline for automated deployments
