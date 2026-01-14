# DC Tech Events - AWS CDK Infrastructure & Deployment Plan

## Overview
Migrate from GitHub Pages hosting to AWS (S3 + CloudFront) with automated deployment via GitHub Actions OIDC federation.

---

## Phase 1: AWS Infrastructure (CDK Stack)

### 1.1 Initial Setup
- [x] Create `infrastructure/` directory at repository root
- [x] Initialize AWS CDK TypeScript project in `infrastructure/`
  - [x] Install CDK CLI: `npm install -g aws-cdk`
  - [x] Initialize stack: `cdk init app --language typescript`
  - [x] Install required CDK packages: `@aws-cdk/aws-s3`, `@aws-cdk/aws-cloudfront`, `@aws-cdk/aws-route53`, `@aws-cdk/aws-iam`, `@aws-cdk/aws-iam-openid-connect`
- [x] Create `lib/dctech-events-stack.ts` with main stack definition
- [x] Create `lib/config.ts` for stack configuration (domain, region, etc.)
- [x] Add `.npmrc` or build scripts to handle dependencies

### 1.2 S3 Bucket
- [x] Create S3 bucket for static site hosting
  - [x] Block all public access
  - [x] Disable versioning
  - [x] Enable encryption at rest
  - [x] Configure origin access control (OAC) for CloudFront
  - [x] Create bucket policy allowing only CloudFront OAC access

### 1.3 CloudFront Distribution
- [x] Create CloudFront distribution
  - [x] Set S3 bucket as origin
  - [x] Configure default root object as `index.html`
  - [x] Cache everything (default TTL: 86400s / 1 day)
  - [x] Redirect HTTP → HTTPS
  - [x] Add security headers via function or behavior policy
  - [x] Compress content automatically
  - [x] Use AWS managed cache policy for optimal performance

### 1.4 SSL/TLS Certificate
- [x] Reference existing ACM certificate for dctech.events
  - [x] Certificate must be in us-east-1 (CloudFront requirement)
  - [x] If doesn't exist, create via CDK

### 1.5 Route53 DNS Records
- [x] Create A record (IPv4) pointing to CloudFront distribution alias
- [x] Create AAAA record (IPv6) pointing to CloudFront distribution alias
- [x] Verify Route53 hosted zone exists for dctech.events
- [ ] Remove existing CNAME record pointing to GitHub Pages (manual CLI step)

### 1.6 GitHub OIDC Federation
- [x] Create OIDC identity provider
  - [x] Provider URL: `https://token.actions.githubusercontent.com`
  - [x] Client ID: `sts.amazonaws.com`
- [x] Create IAM role for GitHub Actions
  - [x] Trust relationship configured for OIDC provider
  - [x] Trust policy scoped to: `repo:owner/dctech.events:ref:refs/heads/main`
  - [x] Role name: `GithubActionsDeployRole`
- [x] Create inline policy for S3 + CloudFront permissions
  - [x] S3 permissions: `s3:PutObject`, `s3:DeleteObject`, `s3:ListBucket` on build bucket
  - [x] CloudFront permissions: `cloudfront:CreateInvalidation` on distribution

### 1.7 Outputs
- [x] Stack output: S3 bucket name
- [x] Stack output: CloudFront distribution ID
- [x] Stack output: CloudFront domain name
- [x] Stack output: OIDC role ARN for GitHub Actions

---

## Phase 2: GitHub Actions Workflow

### 2.1 Deployment Workflow
- [x] Create `.github/workflows/deploy.yml`
  - [x] Trigger: On push to `main` branch
  - [x] Checkout code
  - [x] Set up Node.js
  - [x] Install dependencies: `npm install`
  - [x] Build JavaScript bundles: `npm run build`
  - [x] Set up Python environment
  - [x] Install Python dependencies: `pip install -r requirements.txt`
  - [x] Generate static site: `make all` (or equivalent frozen output)
  - [x] Configure OIDC authentication to AWS
  - [x] Sync built site to S3 bucket
  - [x] Invalidate CloudFront cache
  - [x] Add retry logic for robustness

### 2.2 Workflow Details
- [x] Use `aws-actions/configure-aws-credentials@v4` with OIDC
  - [x] Role to assume: GitHub Actions role ARN from CDK outputs
  - [x] Session name: `github-actions-deploy`
  - [x] Duration: 3600 seconds
- [x] Use AWS CLI to sync `build/` to S3
  - [x] Command: `aws s3 sync build/ s3://bucket-name --delete`
- [x] Use AWS CLI to invalidate CloudFront
  - [x] Command: `aws cloudfront create-invalidation --distribution-id ID --paths "/*"`

### 2.3 Secrets Management
- [x] No secrets needed (pure OIDC federation)
- [x] Store CDK stack outputs in GitHub Actions environment variables or repository settings

---

## Phase 3: Route53 Cleanup

### 3.1 Remove GitHub Pages Records
- [ ] Identify current CNAME record pointing to GitHub Pages
- [ ] Delete CNAME record via AWS CLI
- [ ] Verify DNS resolution points to CloudFront

---

## Phase 4: Deployment & Testing

### 4.1 CDK Deployment
- [ ] Synthesize CDK stack: `cdk synth` in infrastructure/
- [ ] Review CloudFormation template
- [ ] Deploy stack: `cdk deploy` in infrastructure/
  - [ ] Manual approval (not automated)
  - [ ] Verify all resources created
  - [ ] Capture stack outputs
- [ ] Manually store stack outputs (bucket name, distribution ID, role ARN) for GitHub Actions workflow

### 4.2 GitHub Actions Testing
- [ ] Commit and push to `main` branch
- [ ] Verify GitHub Actions workflow triggers
- [ ] Check S3 bucket for uploaded files
- [ ] Check CloudFront shows correct content
- [ ] Test HTTPS access to https://dctech.events
- [ ] Verify HTTP redirects to HTTPS
- [ ] Test cache invalidation (check CloudFront cache statistics)
- [ ] Verify site loads correctly on multiple devices/browsers

### 4.3 Post-Deployment Validation
- [ ] Verify certificate is valid (no warnings)
- [ ] Check CloudFront metrics (requests, bytes transferred, cache hit ratio)
- [ ] Test DNS propagation globally
- [ ] Monitor GitHub Actions logs for issues
- [ ] Set up CloudWatch alarms if needed (optional)

---

## Phase 5: Cleanup & Documentation

### 5.1 Repository Cleanup
- [ ] Remove GitHub Pages settings from repository
- [ ] Remove old GitHub Pages deploy workflow (if exists)
- [ ] Update `README.md` with new deployment process
- [ ] Add `infrastructure/README.md` with CDK documentation
- [ ] Update `.gitignore` to include CDK build artifacts

### 5.2 Documentation
- [ ] Document how to deploy CDK stack locally
- [ ] Document how to view deployment logs from GitHub Actions
- [ ] Document CloudFront cache invalidation (when it happens automatically)
- [ ] Document how to manually redeploy if needed
- [ ] Create runbook for emergency DNS rollback

### 5.3 Decommissioning
- [ ] Verify GitHub Pages is no longer serving traffic
- [ ] Keep GitHub Pages configuration as fallback for 1-2 weeks (optional)
- [ ] Delete GitHub Pages build artifacts once confident in new infrastructure

---

## Technical Stack

| Component | Technology |
|-----------|-----------|
| Infrastructure as Code | AWS CDK (TypeScript) |
| Cloud Provider | AWS (us-east-1) |
| Static Site Hosting | S3 + CloudFront |
| DNS | Route53 |
| Authentication | OIDC Federation (AWS + GitHub) |
| CI/CD | GitHub Actions |
| Site Generation | Flask Frozen (existing `freeze.py`) |

---

## Key Dependencies

- **AWS Account** with Route53 hosted zone for `dctech.events`
- **AWS CLI** configured with credentials
- **CDK CLI** installed globally
- **Node.js 18+** for CDK and JavaScript bundling
- **Python 3.8+** for site generation
- **GitHub repository** with Actions enabled
- **Existing ACM certificate** for `dctech.events` (or auto-create via CDK)

---

## Rollback Plan

1. **CDK Stack Rollback**: Keep `git` history; previous version can be redeployed
2. **DNS Rollback**: Update Route53 A/AAAA records to point elsewhere (if needed)
3. **GitHub Pages Fallback**: Keep branch alive temporarily as backup
4. **Artifact Recovery**: S3 versioning disabled, but CloudFront has cache; old versions available via git tags

---

## Cost Estimates (Monthly)

| Service | Estimated Cost |
|---------|---|
| CloudFront | $20-50 (depending on traffic) |
| S3 | <$1 (minimal storage) |
| Route53 | $0.50 (hosted zone) |
| ACM | Free (AWS issued) |
| IAM/OIDC | Free tier |
| **Total** | **~$20-60/month** |

---

## Success Criteria

- ✅ Site is accessible at https://dctech.events
- ✅ HTTP traffic redirects to HTTPS
- ✅ All static assets load correctly
- ✅ Deployment happens automatically on merge to main
- ✅ CloudFront cache invalidates properly
- ✅ No long-lived AWS credentials in GitHub secrets
- ✅ DNS resolves globally to CloudFront
- ✅ GitHub Pages no longer serving traffic
