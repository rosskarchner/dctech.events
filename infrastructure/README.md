# AWS CDK Infrastructure

This directory contains the AWS Cloud Development Kit (CDK) infrastructure for deploying DC Tech Events to AWS (S3 + CloudFront + Route53).

## Overview

The CDK stack creates the following AWS resources:

- **S3 Bucket**: Static website content hosting with encryption and access control
- **CloudFront Distribution**: Global CDN with HTTPS, compression, and caching
- **ACM Certificate**: HTTPS/TLS certificate for dctech.events domain
- **Route53**: DNS records (A and AAAA) pointing to CloudFront
- **IAM Role**: GitHub Actions OIDC role for automated deployments (no long-lived credentials)

## Project Structure

```
infrastructure/
├── bin/
│   └── infrastructure.ts        # CDK app entry point
├── lib/
│   ├── dctech-events-stack.ts   # Main CDK stack definition
│   └── config.ts                # Stack configuration
├── test/
│   └── infrastructure.test.ts    # CDK unit tests
├── cdk.json                      # CDK configuration
├── package.json                  # Node.js dependencies
├── tsconfig.json                 # TypeScript configuration
└── README.md                     # This file
```

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI v2 configured with credentials
- CDK CLI: `npm install -g aws-cdk`
- Node.js 18+ with npm
- Route53 hosted zone for dctech.events (created in AWS account)

## Configuration

Stack configuration is defined in `lib/config.ts`. Key settings:

```typescript
// Domain and DNS
domain: 'dctech.events'
hostedZoneId: process.env.HOSTED_ZONE_ID // Must be set

// AWS Region (must be us-east-1 for CloudFront certificates)
region: 'us-east-1'

// GitHub OIDC
githubRepositoryOwner: 'dctech-community'
githubRepositoryName: 'dctech.events'
ref: 'ref:refs/heads/main' // Only main branch can deploy

// IAM Role
roleName: 'GithubActionsDeployRole'
sessionName: 'github-actions-deploy'
```

## Deployment Instructions

### 1. Set Environment Variables

```bash
# Set Route53 hosted zone ID (find in AWS console)
export HOSTED_ZONE_ID="Z1234567890ABC"

# Optional: Set existing ACM certificate ARN if available
export ACM_CERTIFICATE_ARN="arn:aws:acm:us-east-1:123456789012:certificate/xxx"
```

### 2. Build TypeScript

```bash
cd infrastructure
npm install
npm run build
```

### 3. Synthesize Stack (Review CloudFormation)

```bash
npm run cdk synth
```

This generates the CloudFormation template. Review the output in `cdk.out/` directory.

### 4. Deploy Stack

```bash
npm run cdk deploy
```

The CDK CLI will:
1. Show resource changes for approval
2. Display the S3 bucket name (format: `dctech-events-site-{timestamp}`)
3. Display the CloudFront distribution ID
4. Display the GitHub Actions IAM role ARN
5. Display any stack outputs

**Important**: Capture these outputs - you'll need them for GitHub Actions configuration.

### 5. Configure GitHub Actions

After CDK deployment, add these repository variables to GitHub:

1. Go to Settings > Secrets and variables > Actions > Repository variables
2. Add these variables:
   - `S3_BUCKET`: The S3 bucket name from CDK outputs
   - `CLOUDFRONT_DISTRIBUTION_ID`: The CloudFront distribution ID from CDK outputs
   - `AWS_ROLE_ARN`: The GitHub Actions IAM role ARN from CDK outputs

## Development Workflow

### Make Changes to Stack

1. Edit `lib/dctech-events-stack.ts` or `lib/config.ts`
2. Build and synthesize:
   ```bash
   npm run build
   npm run cdk synth
   ```
3. Review changes:
   ```bash
   npm run cdk diff
   ```
4. Deploy when satisfied:
   ```bash
   npm run cdk deploy
   ```

### Run Tests

```bash
npm test
```

## Useful Commands

| Command | Description |
|---------|-------------|
| `npm run build` | Compile TypeScript to JavaScript |
| `npm run watch` | Watch for TypeScript changes and recompile |
| `npm test` | Run unit tests |
| `npm run cdk synth` | Synthesize CDK to CloudFormation template |
| `npm run cdk diff` | Show differences between local and deployed stack |
| `npm run cdk deploy` | Deploy stack to AWS |
| `npm run cdk destroy` | Destroy all AWS resources (⚠️ use with caution) |

## Stack Outputs

When deployment completes, the CDK displays these outputs:

- **S3BucketName**: Name of the S3 bucket for site content
- **CloudFrontDistributionId**: ID used for cache invalidation
- **CloudFrontDomainName**: CloudFront domain (e.g., `d123abc.cloudfront.net`)
- **GithubActionsRoleArn**: IAM role ARN for GitHub Actions OIDC

These are also stored in CloudFormation stack exports with these names:
- `DctechEventsBucketName`
- `DctechEventsDistributionId`
- `DctechEventsCloudFrontDomain`
- `DctechEventsGithubActionsRoleArn`

## GitHub Actions Deployment

Once configured with repository variables, GitHub Actions will:

1. Trigger on every push to `main` branch (or on schedule at 6 AM UTC)
2. Build the site using Node.js and Python
3. Authenticate to AWS using OIDC (no stored credentials)
4. Sync built site to S3 bucket
5. Invalidate CloudFront cache (serve new content immediately)

## Troubleshooting

### CloudFormation Deployment Errors

If `cdk deploy` fails:

1. Check AWS account has quota available for resources
2. Verify ACM certificate is in us-east-1 region
3. Check Route53 hosted zone exists and Zone ID is correct
4. Review CloudFormation events in AWS Console for detailed errors

### GitHub Actions Workflow Fails

1. Check OIDC role exists in AWS IAM
2. Verify repository variables are set correctly
3. Check GitHub Actions logs for specific error messages
4. Ensure main branch can assume the OIDC role

### DNS Not Resolving

1. Verify Route53 A and AAAA records exist
2. Check that old CNAME record pointing to GitHub Pages is deleted
3. Allow 5-10 minutes for DNS propagation
4. Use `dig dctech.events` or online DNS checker to verify

## Cost Estimation

Monthly costs (approximate):

| Service | Cost |
|---------|------|
| CloudFront | $20-50 (depends on traffic) |
| S3 | <$1 (minimal storage) |
| Route53 | $0.50 (hosted zone) |
| ACM | Free (AWS-issued certificates) |
| OIDC/IAM | Free tier |
| **Total** | **~$20-60/month** |

## Security Considerations

- ✅ No long-lived AWS credentials stored in GitHub
- ✅ OIDC federation limited to main branch only
- ✅ S3 bucket blocks all public access
- ✅ CloudFront enforces HTTPS only
- ✅ TLS 1.2+ required
- ⚠️ Ensure ACM certificate is valid and renewed automatically

## Rollback Plan

If issues occur:

1. **Fast Rollback (DNS)**: Update Route53 records to point elsewhere temporarily
2. **GitHub Pages Fallback**: Revert DNS to GitHub Pages temporarily
3. **Revert CDK**: Use git history to revert to previous version and redeploy
4. **AWS Rollback**: Use CloudFormation stack history to roll back resources

## Additional Resources

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [CloudFront Best Practices](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/)
- [Route53 Hosted Zone Guide](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/hosted-zones-working-with.html)
- [GitHub OIDC in AWS](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)

## Support

For infrastructure issues:
1. Check CDK synthesis errors first
2. Review AWS CloudFormation events in AWS Console
3. Check GitHub Actions workflow logs for deployment issues
4. Consult AWS documentation for service-specific errors