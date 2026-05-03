# Multi-Site Infrastructure Configuration

## Overview

Extended `infrastructure/lib/config.ts` to support multiple sites (DC Tech Events and DC STEM Events) while sharing common infrastructure components.

## Architecture

### Configuration Structure

```
sharedConfig (region, GitHub OIDC, IAM, DynamoDB, tags, Chalice, features)
    ↓
dctechSiteConfig (site-specific: domain, S3, CloudFront, Cognito, secrets, etc.)
dcstemSiteConfig (site-specific: domain, S3, CloudFront, Cognito, secrets, etc.)
    ↓
sitesConfig = { dctech, dcstem }
    ↓
stackConfig = sharedConfig + dctechSiteConfig (backward compatible)
```

## Shared Configuration (sharedConfig)

All sites share:

- **Region**: `us-east-1` (CloudFront requirement)
- **GitHub OIDC**: Single identity provider for all sites (reposskarchner/dctech.events)
- **IAM Role**: `GithubActionsDeployRole` (shared across all sites)
- **DynamoDB**: `DcTechEvents` table (single table for all sites)
- **Tags**: `project: dctech-events`, `environment: production`, `managedBy: CDK`
- **Chalice API**: Legacy API configuration
- **Feature Flags**: Custom domain support enabled

## Site-Specific Configurations

### DC Tech Events (dctechSiteConfig)

**Domain & DNS:**
- Domain: `dctech.events`
- Hosted Zone ID: `Z078066931R85FQDWCM3P`
- Redirects: `dctechevents.com` → `dctech.events`

**S3 Buckets:**
- Site: `dctech-events-site-1768361440101`
- Data Cache: `dctech-events-data-cache`

**CloudFront:**
- TTLs: min=0, default=1d, max=1yr
- HTTP: 2/3
- Compression: Enabled
- WAF Web ACL: Existing WAF ARN (production pricing plan)

**Cognito:**
- User Pool: `dctech-events-users`
- Domain Prefix: `dctech-events`
- Custom Domain: `login.dctech.events`
- Callback URLs: `/edit/auth/callback.html` (dctech.events and www)
- SES: `noreply@dctech.events`

**Secrets:**
- Cognito Client Secret: `dctech-events/cognito-client-secret`
- Microblog Token: `dctech-events/microblog-token`
- GitHub Token: `dctech-events/github-token`

**Newsletter:**
- Schedule: Monday 12:00 UTC (7 AM EST / 11 AM EDT)

**Rebuild Queue:**
- Queue Name: `dctech-events-rebuild.fifo`
- Timeout: 900s, Memory: 1024MB

### DC STEM Events (dcstemSiteConfig)

**Domain & DNS:**
- Domain: `dc.localstem.events`
- Hosted Zone ID: `""` (TODO: Update with actual Route53 zone)
- No redirect domains (can be added later)

**S3 Buckets:**
- Site: `dcstem-events-site-1768361440101`
- Data Cache: `dcstem-events-data-cache`

**CloudFront:**
- Same TTLs and settings as dctech
- WAF Web ACL: `""` (TODO: Provide or create new WAF ACL)

**Cognito:**
- User Pool: `dcstem-events-users`
- Domain Prefix: `dcstem-events`
- Custom Domain: `login.dc.localstem.events`
- Callback URLs: `/edit/auth/callback.html` (dc.localstem.events and www)
- SES: `noreply@dc.localstem.events`

**Secrets:**
- Cognito Client Secret: `dcstem-events/cognito-client-secret`
- Microblog Token: `dcstem-events/microblog-token`
- GitHub Token: `dcstem-events/github-token`

**Rebuild Queue:**
- Queue Name: `dcstem-events-rebuild.fifo`
- Timeout: 900s, Memory: 1024MB

## Usage

### Access Configurations

```typescript
import { stackConfig, sitesConfig, sharedConfig, dctechSiteConfig, dcstemSiteConfig } from './config';

// Original usage (backward compatible)
stackConfig.domain // → 'dctech.events'
stackConfig.region // → 'us-east-1'

// New multi-site usage
sitesConfig.dctech.domain // → 'dctech.events'
sitesConfig.dcstem.domain // → 'dc.localstem.events'

// Shared config
sharedConfig.github.repositoryOwner // → 'rosskarchner'
sharedConfig.dynamodb.tableName // → 'DcTechEvents'

// Individual site configs
dctechSiteConfig.s3.bucketName // → 'dctech-events-site-1768361440101'
dcstemSiteConfig.s3.bucketName // → 'dcstem-events-site-1768361440101'
```

### Future Enhancement: Multi-Site Stack

When modifying stack definitions to support multiple sites:

```typescript
// For multiple stacks approach:
Object.entries(sitesConfig).forEach(([siteId, siteConfig]) => {
  new SiteStack(app, siteConfig.stackName, {
    env: { region: sharedConfig.region },
    siteConfig,
    sharedConfig,
  });
});
```

## TODOs for dcstem Configuration

1. **Route53 Hosted Zone:**
   - [ ] Create or identify Route53 hosted zone for `dc.localstem.events`
   - [ ] Update `dcstemSiteConfig.hostedZoneId` with Zone ID

2. **CloudFront WAF:**
   - [ ] Create CloudFront WAF Web ACL for dcstem (or use shared WAF)
   - [ ] Update `dcstemSiteConfig.cloudfront.webAclId` with ARN

3. **ACM Certificate:**
   - [ ] Create ACM certificate for `dc.localstem.events` in us-east-1
   - [ ] Update `dcstemSiteConfig.acm.existingCertificateArn` with certificate ARN
   - [ ] Or let CDK auto-create with DNS validation

4. **Cognito Setup:**
   - [ ] Create Cognito user pool and domain for dcstem
   - [ ] Configure SES for emails (may need setup if not in production account)
   - [ ] Update SES sender email if needed

5. **Secrets Manager:**
   - [ ] Store Cognito client secret in `dcstem-events/cognito-client-secret`
   - [ ] Store microblog token (if used) in `dcstem-events/microblog-token`
   - [ ] Store GitHub token (if used) in `dcstem-events/github-token`

## Backward Compatibility

✓ **Fully backward compatible** — existing code uses `stackConfig` which is automatically merged from `sharedConfig + dctechSiteConfig`. No changes required to existing infrastructure code.

Example: `bin/infrastructure.ts` continues to work without modification:
- `stackConfig.stackName` → 'dctech-events'
- `stackConfig.region` → 'us-east-1'
- `stackConfig.domain` → 'dctech.events'
- All shared properties accessible as before

## TypeScript Compilation

✓ Configuration compiles successfully:
```bash
cd infrastructure
npm run build
# → No errors
```

## Next Steps

1. Update infrastructure/bin/infrastructure.ts to optionally instantiate dcstem stack
2. Create DcTechEventsStemStack or modify existing stack to be site-aware
3. Add environment variable or parameter to control which sites to deploy
4. Fill in dcstem TODOs (hosted zone, WAF, certificates, etc.)
5. Test multi-site deployment

