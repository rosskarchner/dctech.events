# AWS Deployment Runbook

This document provides step-by-step instructions for deploying DC Tech Events from GitHub Pages to AWS.

## Prerequisites

Before starting, ensure you have:

- AWS account with appropriate IAM permissions
- AWS CLI v2 installed and configured
- Route53 hosted zone for dctech.events already created
- CDK CLI installed globally: `npm install -g aws-cdk`
- Repository cloned and all changes committed to main branch

## Phase 1: Infrastructure Deployment

### Step 1: Prepare Environment

```bash
# Clone repository and navigate to infrastructure directory
cd infrastructure

# Install dependencies
npm install

# Set required environment variables
export HOSTED_ZONE_ID="Z1234567890ABC"  # Get from AWS Route53 console
export AWS_REGION="us-east-1"

# Optional: If you have existing ACM certificate
export ACM_CERTIFICATE_ARN="arn:aws:acm:us-east-1:123456789012:certificate/xxx"
```

### Step 2: Build and Review

```bash
# Build TypeScript
npm run build

# Synthesize CloudFormation template
npm run cdk synth

# Review the synthesized template
cat cdk.out/dctech-events.template.json | head -100

# Check differences if redeploying
npm run cdk diff
```

### Step 3: Deploy Stack

```bash
# Deploy stack to AWS
npm run cdk deploy

# When prompted, review the changes and type 'y' to proceed
# Wait for deployment to complete (5-10 minutes typically)
```

**⚠️ Important: Capture the output values:**

```
Outputs:
S3BucketName = dctech-events-site-1234567890
CloudFrontDistributionId = E1A2B3C4D5E6F7
CloudFrontDomainName = d1a2b3c4d5e6f7.cloudfront.net
GithubActionsRoleArn = arn:aws:iam::123456789012:role/GithubActionsDeployRole
```

Save these values - you'll need them in the next phase.

## Phase 2: GitHub Configuration

### Step 4: Create Repository Variables

1. Go to GitHub repository Settings
2. Navigate to Secrets and variables > Actions > Repository variables
3. Create three new repository variables (NOT secrets):

| Variable Name | Value |
|---------------|-------|
| `S3_BUCKET` | The S3 bucket name from step 3 output |
| `CLOUDFRONT_DISTRIBUTION_ID` | The CloudFront distribution ID from step 3 output |
| `AWS_ROLE_ARN` | The GitHub Actions role ARN from step 3 output |

Example:
- S3_BUCKET = `dctech-events-site-1768355683355`
- CLOUDFRONT_DISTRIBUTION_ID = `E1A2B3C4D5E6F`
- AWS_ROLE_ARN = `arn:aws:iam::123456789012:role/GithubActionsDeployRole`

### Step 5: Test GitHub Actions

```bash
# Commit and push to main to trigger workflow
git push origin main

# Monitor GitHub Actions
# Go to Actions tab in GitHub repository
# Watch the "Deploy to AWS" workflow execute
```

Check workflow logs for:
- ✅ Successful checkout
- ✅ Node.js dependencies installed
- ✅ JavaScript bundles built
- ✅ Python dependencies installed
- ✅ Static site generated via `make all`
- ✅ AWS credentials configured
- ✅ Files synced to S3
- ✅ CloudFront cache invalidated

## Phase 3: DNS Cutover

### Step 6: Identify Current DNS Configuration

```bash
# Check current DNS records for dctech.events
dig dctech.events
dig dctech.events AAAA

# Expected output (currently GitHub Pages):
# dctech.events. 300 IN CNAME github.io.
```

### Step 7: Update Route53 Records

The CDK stack already created A and AAAA records pointing to CloudFront. Verify they exist:

```bash
# List Route53 records
aws route53 list-resource-record-sets \
  --hosted-zone-id $HOSTED_ZONE_ID \
  --query 'ResourceRecordSets[?Name==`dctech.events.`]'
```

Expected output:
```json
[
  {
    "Name": "dctech.events.",
    "Type": "A",
    "AliasTarget": {
      "HostedZoneId": "Z2FDTNDATAQYW2",  # CloudFront zone ID
      "DNSName": "d1a2b3c4d5e6f7.cloudfront.net",
      "EvaluateTargetHealth": false
    }
  },
  {
    "Name": "dctech.events.",
    "Type": "AAAA",
    "AliasTarget": {
      "HostedZoneId": "Z2FDTNDATAQYW2",
      "DNSName": "d1a2b3c4d5e6f7.cloudfront.net",
      "EvaluateTargetHealth": false
    }
  }
]
```

### Step 8: Remove Old CNAME Record (if exists)

If you still have the GitHub Pages CNAME record, delete it:

```bash
# Find the CNAME record ID (if it exists)
aws route53 list-resource-record-sets \
  --hosted-zone-id $HOSTED_ZONE_ID \
  --query 'ResourceRecordSets[?Type==`CNAME`]'

# Delete the CNAME record if it exists
aws route53 change-resource-record-sets \
  --hosted-zone-id $HOSTED_ZONE_ID \
  --change-batch '{
    "Changes": [{
      "Action": "DELETE",
      "ResourceRecordSet": {
        "Name": "dctech.events",
        "Type": "CNAME",
        "TTL": 300,
        "ResourceRecords": [{"Value": "rosskarchner.github.io"}]
      }
    }]
  }'
```

### Step 9: Verify DNS Propagation

```bash
# Check DNS resolution immediately (may show old record due to TTL)
dig dctech.events

# Check with specific nameserver
dig @8.8.8.8 dctech.events

# Use online tools for global propagation check
# https://www.whatsmydns.net/?d=dctech.events
```

**Allow 5-10 minutes for DNS changes to propagate globally.**

## Phase 4: Website Testing

### Step 10: Test HTTPS Access

```bash
# Test with curl
curl -I https://dctech.events/
# Expected: HTTP/1.1 200 OK or 301/302 redirect

# Test HTTP redirect
curl -I http://dctech.events/
# Expected: HTTP/1.1 301 Moved Permanently
# Location: https://dctech.events/
```

### Step 11: Verify Certificate

```bash
# Check certificate validity
openssl s_client -connect dctech.events:443 -servername dctech.events </dev/null

# Look for:
# ✅ Verify return code: 0 (ok)
# ✅ Subject: CN=dctech.events
# ✅ Not Before/Not After dates are valid
```

### Step 12: Manual Testing Checklist

Perform these tests in a browser:

- [ ] Visit https://dctech.events - loads without SSL warnings
- [ ] Homepage displays correctly
- [ ] Navigation to /categories/python works
- [ ] Event listings display with images and details
- [ ] /submit form loads (GitHub auth available)
- [ ] /edit/{event_id} form loads with pre-populated data
- [ ] Mobile responsive design works
- [ ] Test on multiple browsers (Chrome, Firefox, Safari, Edge)

### Step 13: Performance Testing

```bash
# Check CloudFront caching
curl -I https://dctech.events/
# Look for X-Cache header (HIT/MISS)
# On second request should be HIT

# Check metrics in AWS console
# CloudWatch > CloudFront > Monitoring
# - Requests (should show recent requests)
# - Bytes Downloaded
# - Cache Hit Rate (should be >80%)
```

## Phase 5: GitHub Pages Cleanup (Optional)

### Step 14: Disable GitHub Pages

1. Go to repository Settings
2. Navigate to Pages section
3. Change Source from "Deploy from a branch" to "None"
4. Delete the gh-pages branch if it exists:
   ```bash
   git push origin --delete gh-pages
   ```

### Step 15: Verify GitHub Pages is Offline

```bash
# GitHub Pages domain should no longer respond
curl -I https://rosskarchner.github.io/dctech.events/
# Expected: 404 Not Found or connection refused
```

## Rollback Procedures

### Quick DNS Rollback

If something goes wrong, you can quickly revert to GitHub Pages:

```bash
# Update Route53 to point back to GitHub Pages
aws route53 change-resource-record-sets \
  --hosted-zone-id $HOSTED_ZONE_ID \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "dctech.events",
        "Type": "CNAME",
        "TTL": 300,
        "ResourceRecords": [{"Value": "rosskarchner.github.io"}]
      }
    }]
  }'

# You must DELETE the A and AAAA records first
aws route53 change-resource-record-sets \
  --hosted-zone-id $HOSTED_ZONE_ID \
  --change-batch '{
    "Changes": [
      {"Action": "DELETE", "ResourceRecordSet": {"Name": "dctech.events", "Type": "A", ...}},
      {"Action": "DELETE", "ResourceRecordSet": {"Name": "dctech.events", "Type": "AAAA", ...}}
    ]
  }'
```

### Full Stack Rollback

To completely remove AWS infrastructure:

```bash
cd infrastructure
npm run cdk destroy
```

⚠️ **Warning**: This will delete:
- S3 bucket and all uploaded files
- CloudFront distribution
- ACM certificate
- IAM role
- Route53 records created by CDK

## Monitoring Post-Deployment

### CloudWatch Metrics

Monitor these in AWS CloudWatch:

- CloudFront requests and bytes
- S3 bucket size
- HTTP error rates

### GitHub Actions

Monitor workflow runs:

1. Go to Actions tab
2. Check "Deploy to AWS" workflow
3. Review logs for any errors
4. Set up notifications for failed deployments

### DNS Monitoring

```bash
# Schedule regular DNS checks
while true; do
  date
  dig dctech.events +short
  sleep 300
done
```

## Troubleshooting

### SSL Certificate Warnings

**Problem**: Browser shows untrusted certificate warning

**Solutions**:
1. Verify certificate is valid for dctech.events
2. Clear browser cache and cookies
3. Wait for DNS propagation to complete
4. Use different DNS server: `dig @1.1.1.1 dctech.events`

### S3 Sync Fails

**Problem**: GitHub Actions workflow fails on S3 sync step

**Solutions**:
1. Verify repository variables are set correctly
2. Check OIDC role has correct S3 permissions
3. Verify S3 bucket exists and is accessible
4. Check role trust policy includes GitHub Actions principal

### CloudFront Cache Not Invalidating

**Problem**: Old content still shows after deployment

**Solutions**:
1. Manually invalidate from AWS console
2. Verify distribution ID is correct
3. Check OIDC role has cloudfront:CreateInvalidation permission
4. Wait for current cache TTL to expire (default 1 day)

### DNS Resolution Fails

**Problem**: Domain doesn't resolve to CloudFront

**Solutions**:
1. Verify Route53 A and AAAA records exist
2. Delete old CNAME record if it exists
3. Check hosted zone ID is correct
4. Wait 5-10 minutes for propagation
5. Try different DNS servers: 8.8.8.8, 1.1.1.1

## Success Criteria Checklist

- [x] CDK stack deployed to AWS
- [x] GitHub Actions repository variables configured
- [x] GitHub Actions workflow runs successfully
- [x] Files synced to S3 bucket
- [x] CloudFront distribution serving content
- [x] Route53 DNS records point to CloudFront
- [x] HTTPS works without certificate warnings
- [x] HTTP redirects to HTTPS
- [x] Homepage loads correctly
- [x] All pages render properly
- [x] Mobile responsive design works
- [x] No JavaScript console errors
- [x] CloudFront cache hit rate >80%
- [x] GitHub Pages no longer serving traffic

## Support

If you encounter issues:

1. Check CloudFormation stack events in AWS Console
2. Review GitHub Actions workflow logs
3. Check AWS IAM permissions
4. Verify DNS propagation globally
5. Consult AWS documentation for specific services
6. Review infrastructure/README.md troubleshooting section
