# LocalTech.Events Infrastructure Guide

This document explains the AWS infrastructure for localtech.events and how to deploy it.

## Overview

LocalTech.Events uses a serverless architecture on AWS to host multiple city sites under a single domain with subdomain routing:

- **Apex domain**: `localtech.events` → City directory homepage
- **City subdomains**: `{city}.localtech.events` → City-specific event sites

## Architecture Components

### 1. S3 Bucket
- **Purpose**: Static website hosting
- **Structure**:
  ```
  s3://localtech-events-hosting/
  ├── index.html              # Homepage (city directory)
  ├── dc/                     # Washington DC site
  │   ├── index.html
  │   ├── groups/
  │   └── ...
  ├── baltimore/              # Baltimore site
  │   ├── index.html
  │   └── ...
  └── philadelphia/           # Philadelphia site
      └── ...
  ```
- **Access**: Private bucket with Origin Access Control (OAC)

### 2. CloudFront Distribution
- **Purpose**: Global CDN with subdomain routing
- **Features**:
  - Custom domain with SSL/TLS (ACM certificate)
  - CloudFront Function for request routing
  - Gzip/Brotli compression
  - Cache invalidation on deployment

**Routing Logic** (CloudFront Function):
```javascript
// localtech.events → /index.html
// dc.localtech.events → /dc/index.html
// baltimore.localtech.events → /baltimore/index.html
```

### 3. ACM Certificate
- **Domain**: `*.localtech.events` and `localtech.events`
- **Validation**: DNS validation via Route53
- **Region**: `us-east-1` (required for CloudFront)

### 4. Route53
- **Purpose**: DNS management
- **Records**:
  - `A` + `AAAA` for apex domain → CloudFront
  - `A` + `AAAA` for wildcard `*.localtech.events` → CloudFront

### 5. IAM Resources
- **Deployment User**: `localtech-github-actions-deployer`
  - Created automatically by CDK stack
  - **Unified user for ALL GitHub Actions deployments** (static site + OAuth endpoint)
  - Replaces need for separate AWS credentials
- **Managed Policy**: `LocalTechDeploymentPolicy`
  - Attached to deployment user
  - **Static Site Deployment Permissions**:
    - **S3 Bucket**: `s3:ListBucket`, `s3:GetBucketLocation`
    - **S3 Objects**: `s3:PutObject`, `s3:PutObjectAcl`, `s3:GetObject`, `s3:DeleteObject`
    - **CloudFront**: `cloudfront:CreateInvalidation`, `cloudfront:GetInvalidation`, `cloudfront:ListInvalidations`
  - **OAuth Endpoint (Chalice) Deployment Permissions**:
    - **Lambda**: Create, update, delete functions
    - **API Gateway**: Full REST API management
    - **IAM**: Create/manage Lambda execution roles
    - **Secrets Manager**: Read GitHub OAuth secrets
    - **CloudFormation**: Manage Chalice stacks
    - **CloudWatch Logs**: Access Lambda logs
  - All permissions scoped to specific resources (least privilege)

## Prerequisites

Before deploying infrastructure, you need:

1. **AWS Account** with appropriate permissions
2. **AWS CLI** configured with credentials
3. **Domain registered** in Route53 or DNS configured to Route53
4. **Node.js 20+** for CDK

## Infrastructure as Code (CDK)

The infrastructure is defined using AWS CDK (TypeScript) in the `infrastructure/` directory.

### File Structure

```
infrastructure/
├── bin/
│   └── app.ts                  # CDK app entry point
├── lib/
│   ├── localtech-stack.ts      # Main stack definition
│   └── origin-request-function.js  # CloudFront Function code
├── package.json                # Dependencies
├── tsconfig.json               # TypeScript config
└── cdk.json                    # CDK configuration
```

### Stack Resources

The `LocalTechStack` creates:

1. **S3 Bucket** (`localtech-events-hosting`)
   - Versioning enabled
   - Block public access
   - Origin Access Control for CloudFront

2. **CloudFront Distribution**
   - S3 origin with OAC
   - Custom domain: `localtech.events` and `*.localtech.events`
   - CloudFront Function for routing
   - Price class: PriceClass100 (NA + Europe)

3. **ACM Certificate**
   - Subject Alternative Names: apex + wildcard
   - DNS validation

4. **Route53 Records**
   - A record (IPv4) for apex
   - AAAA record (IPv6) for apex
   - A record (IPv4) for wildcard
   - AAAA record (IPv6) for wildcard

5. **IAM User and Policy**
   - IAM User: `localtech-github-actions-deployer`
   - Managed Policy: `LocalTechDeploymentPolicy`
   - **Unified credentials** for both static site and OAuth endpoint deployments
   - Scoped permissions for S3, CloudFront, Lambda, API Gateway, CloudFormation, and Secrets Manager

## Deployment Instructions

### Initial Setup

1. **Install dependencies**:
   ```bash
   cd infrastructure
   npm install
   ```

2. **Configure AWS credentials**:
   ```bash
   aws configure
   # Enter your AWS Access Key ID, Secret Access Key, and region (us-east-1)
   ```

3. **Bootstrap CDK** (first time only):
   ```bash
   npx cdk bootstrap aws://ACCOUNT-ID/us-east-1
   ```

### Deploy Infrastructure

1. **Review changes** (recommended):
   ```bash
   npx cdk diff
   ```

2. **Deploy stack**:
   ```bash
   npx cdk deploy
   ```

3. **Note the outputs**:
   ```
   Outputs:
   LocalTechStack.BucketName = localtech-events-hosting
   LocalTechStack.DistributionId = E1234ABCDEFGH
   LocalTechStack.DistributionDomain = d1234abcd.cloudfront.net
   LocalTechStack.DeploymentUserName = localtech-github-actions-deployer
   LocalTechStack.DeploymentUserArn = arn:aws:iam::123456789:user/localtech-github-actions-deployer
   LocalTechStack.ApexDomain = https://localtech.events
   ```

4. **Create access keys for the deployment user**:
   ```bash
   # The CDK stack created an IAM user: localtech-github-actions-deployer
   # Create access keys for this user:
   aws iam create-access-key --user-name localtech-github-actions-deployer
   ```

   This will output:
   ```json
   {
     "AccessKey": {
       "UserName": "localtech-github-actions-deployer",
       "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
       "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
       "Status": "Active",
       "CreateDate": "2025-01-01T00:00:00Z"
     }
   }
   ```

   **⚠️ Important**: Save the `SecretAccessKey` immediately! It will only be shown once.

5. **Add GitHub Secrets**:

   Go to: `https://github.com/YOUR_REPO/settings/secrets/actions`

   Add these secrets:
   - `AWS_ACCESS_KEY_ID` = The AccessKeyId from step 4
   - `AWS_SECRET_ACCESS_KEY` = The SecretAccessKey from step 4
   - `CLOUDFRONT_DISTRIBUTION_ID` = The DistributionId from step 3
   - `S3_BUCKET_NAME` = The BucketName from step 3

   Example:
   ```
   AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
   AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
   CLOUDFRONT_DISTRIBUTION_ID=E1234ABCDEFGH
   S3_BUCKET_NAME=localtech-events-hosting
   ```

   **Note**: These same credentials are used by **all GitHub Actions workflows**:
   - `deploy-localtech.yml` - Static site deployment
   - `deploy-oauth.yml` - OAuth endpoint deployment
   - `deploy-infrastructure.yml` - Infrastructure updates

   This unified approach means you only need one set of AWS credentials!

### Verify Deployment

1. **Check CloudFront distribution**:
   ```bash
   aws cloudfront get-distribution --id E1234ABCDEFGH
   ```

2. **Test DNS resolution**:
   ```bash
   dig localtech.events
   dig baltimore.localtech.events
   ```

3. **Test routing** (after uploading content):
   ```bash
   curl -I https://localtech.events/
   curl -I https://dc.localtech.events/
   ```

## Updating Infrastructure

### Modify CDK Code

1. Edit `infrastructure/lib/localtech-stack.ts`
2. Test locally:
   ```bash
   npx cdk synth
   ```
3. Review changes:
   ```bash
   npx cdk diff
   ```
4. Deploy:
   ```bash
   npx cdk deploy
   ```

### Automated Deployment

Infrastructure changes are automatically deployed via GitHub Actions when:
- Files in `infrastructure/**` are modified
- Manual workflow dispatch

See `.github/workflows/deploy-infrastructure.yml`

## Content Deployment

### Manual Upload

```bash
# Build all cities
make homepage
CITY=dc make all
CITY=baltimore make all

# Sync to S3
aws s3 sync build-all/ s3://localtech-events-hosting/ \
  --delete \
  --cache-control "public, max-age=300"

# Invalidate cache
aws cloudfront create-invalidation \
  --distribution-id E1234ABCDEFGH \
  --paths "/*"
```

### Automated Deployment

Content is automatically built and deployed via GitHub Actions:
- **Trigger**: Push to main, daily cron, manual dispatch
- **Workflow**: `.github/workflows/deploy-localtech.yml`
- **Process**:
  1. Build homepage
  2. Build all cities
  3. Sync to S3
  4. Invalidate CloudFront cache

## CloudFront Function Routing

The routing logic is implemented in `infrastructure/lib/origin-request-function.js`:

```javascript
function handler(event) {
    var request = event.request;
    var host = request.headers.host.value;

    // Extract subdomain
    var subdomain = host.split('.')[0];

    if (subdomain === 'localtech') {
        // Apex domain - serve homepage
        request.uri = '/index.html';
    } else {
        // Subdomain - serve city site
        // dc.localtech.events → /dc/index.html
        request.uri = '/' + subdomain + request.uri;

        // Default to index.html if directory
        if (request.uri.endsWith('/')) {
            request.uri += 'index.html';
        }
    }

    return request;
}
```

## Monitoring and Logs

### CloudFront Metrics

View in AWS Console:
- Requests
- Error rate (4xx, 5xx)
- Data transfer
- Cache hit ratio

### CloudFront Logs

Enable standard logs in CloudFront settings:
```bash
aws cloudfront get-distribution-config --id E1234ABCDEFGH
```

### S3 Access Logs

Enable S3 bucket logging:
```typescript
// In localtech-stack.ts
bucket.addPropertyOverride('LoggingConfiguration', {
  DestinationBucketName: 'my-logs-bucket',
  LogFilePrefix: 'localtech-events/'
});
```

## Cost Estimation

Monthly costs (estimated):

- **S3 Storage**: $0.023/GB (~$1-5/month for static sites)
- **CloudFront**: $0.085/GB for first 10TB (~$5-20/month)
- **Route53**: $0.50/hosted zone + $0.40/million queries (~$1/month)
- **ACM Certificate**: Free
- **Data Transfer**: Varies by traffic

**Total**: ~$10-30/month for moderate traffic

## Security

### S3 Bucket Security
- ✅ Public access blocked
- ✅ Origin Access Control (OAC) for CloudFront
- ✅ Versioning enabled
- ✅ Encryption at rest (SSE-S3)

### CloudFront Security
- ✅ HTTPS required (HTTP → HTTPS redirect)
- ✅ TLS 1.2+ only
- ✅ Security headers (via CloudFront Functions)
- ✅ Origin Access Control

### DNS Security
- ✅ DNSSEC (optional, can be enabled in Route53)

## Troubleshooting

### Certificate Validation Stuck

**Issue**: ACM certificate pending validation

**Solution**:
```bash
# Check certificate status
aws acm describe-certificate --certificate-arn arn:aws:acm:...

# Verify DNS records exist in Route53
aws route53 list-resource-record-sets --hosted-zone-id Z1234...
```

### CloudFront 403 Errors

**Issue**: Access denied when accessing content

**Solutions**:
1. Check S3 bucket policy allows CloudFront OAC
2. Verify files exist in S3: `aws s3 ls s3://localtech-events-hosting/`
3. Check CloudFront Function logs

### Subdomain Not Routing

**Issue**: `baltimore.localtech.events` returns 404

**Solutions**:
1. Verify DNS: `dig baltimore.localtech.events`
2. Check CloudFront Function code
3. Verify S3 path exists: `aws s3 ls s3://localtech-events-hosting/baltimore/`

### Cache Not Invalidating

**Issue**: Old content still showing

**Solutions**:
```bash
# Create invalidation
aws cloudfront create-invalidation \
  --distribution-id E1234ABCDEFGH \
  --paths "/*"

# Check invalidation status
aws cloudfront get-invalidation \
  --distribution-id E1234ABCDEFGH \
  --id I1234ABCD
```

## Disaster Recovery

### Backup Strategy

1. **S3 Versioning**: Enabled on bucket (can restore previous versions)
2. **CDK Code**: Version controlled in Git
3. **DNS Records**: Exported via Route53 zone export

### Recovery Procedures

**If S3 bucket is deleted**:
```bash
# Redeploy infrastructure
cd infrastructure
npx cdk deploy

# Rebuild and upload all content
make homepage
for city in dc baltimore philadelphia pittsburgh richmond; do
  CITY=$city make all
done

# Upload to S3
aws s3 sync build-all/ s3://localtech-events-hosting/
```

**If CloudFront distribution is deleted**:
```bash
# Redeploy infrastructure (will recreate distribution)
cd infrastructure
npx cdk deploy

# Update GitHub Secrets with new distribution ID
```

## Advanced Configuration

### Custom Domains

To add a custom domain (e.g., `custom-city.events`):

1. Add domain to ACM certificate
2. Update CloudFront distribution alternate domain names
3. Create Route53 records or CNAME in external DNS

### WAF Integration

To add AWS WAF for DDoS protection:

```typescript
// In localtech-stack.ts
import * as wafv2 from 'aws-cdk-lib/aws-wafv2';

const webAcl = new wafv2.CfnWebACL(this, 'WebACL', {
  scope: 'CLOUDFRONT',
  defaultAction: { allow: {} },
  visibilityConfig: {
    sampledRequestsEnabled: true,
    cloudWatchMetricsEnabled: true,
    metricName: 'LocalTechWebACL'
  },
  rules: [/* rate limiting rules */]
});

// Associate with CloudFront
distribution.addPropertyOverride('DistributionConfig.WebACLId', webAcl.attrArn);
```

### Lambda@Edge for Advanced Routing

For more complex routing, replace CloudFront Function with Lambda@Edge:

```typescript
import * as lambda from 'aws-cdk-lib/aws-lambda';

const edgeLambda = new lambda.Function(this, 'EdgeFunction', {
  runtime: lambda.Runtime.NODEJS_20_X,
  handler: 'index.handler',
  code: lambda.Code.fromAsset('lambda')
});

// Add to CloudFront as viewer request
```

## References

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [CloudFront Functions](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cloudfront-functions.html)
- [Route53 DNS](https://docs.aws.amazon.com/route53/)
- [ACM Certificates](https://docs.aws.amazon.com/acm/)

## Support

For issues with infrastructure:
1. Check troubleshooting section above
2. Review CloudWatch logs
3. Open GitHub issue with `infrastructure` label
