# Testing and Deployment Checklist

This checklist helps verify the event tracking and RSS feed functionality after deployment.

## Pre-Deployment

### 1. Update Infrastructure (One-time)

The CDK stack needs to be redeployed to add the `s3:GetObject` permission:

```bash
cd infrastructure
npm install
npm run build
npm run cdk deploy
```

Confirm the role has these S3 permissions:
- `s3:GetObject`
- `s3:PutObject`
- `s3:DeleteObject`
- `s3:ListBucket`

### 2. Verify Environment Variables

Check GitHub repository settings (Settings > Secrets and variables > Actions):

**Repository Variables** (should already exist):
- `S3_BUCKET`: S3 bucket name
- `CLOUDFRONT_DISTRIBUTION_ID`: CloudFront distribution ID
- `AWS_ROLE_ARN`: GitHub Actions IAM role ARN
- `MICROBLOG_DESTINATION`: Micro.blog destination URL

**Repository Secrets** (should already exist):
- `MB_TOKEN`: Micro.blog app token

## Post-Deployment Testing

### 1. Verify Event Tracking

After the first deployment with these changes:

```bash
# Check S3 bucket for new files
aws s3 ls s3://YOUR-BUCKET-NAME/upcoming-history/

# Expected files:
# - upcoming-history/YYYY-MM-DD-HH-MM-SS.yaml
# - upcoming-history/latest.yaml
# - upcoming-history/metadata.json
```

### 2. Test RSS Feed

Visit: `https://dctech.events/events-feed.xml`

Expected:
- Valid RSS 2.0 XML
- Channel title: "DC Tech Events - New Events"
- Items (if any events added in last 30 days)

Test with RSS reader:
- Subscribe to the feed
- Verify events appear correctly

### 3. Test Daily Summary Workflow

Trigger manually from GitHub Actions:

1. Go to Actions > "Post Daily Event Summary to Micro.blog"
2. Click "Run workflow"
3. Options:
   - `dry_run`: true (for testing)
   - `date`: Leave empty for today, or specify YYYY-MM-DD

Check workflow logs for:
- ✓ Successfully authenticated to AWS
- ✓ Downloaded metadata from S3
- ✓ Found N events added on [date]
- ✓ Would post to micro.blog (if dry run)

### 4. Verify Micro.blog Posting

After confirming dry run works:

1. Run workflow again without dry_run
2. Check micro.blog destination for new post
3. Verify post title: "X new events added on [Month Day Year]"
4. Verify post contains event list with links

## Monitoring

### GitHub Actions

Monitor these workflows:
- **Deploy to AWS**: Should run successfully after each push to main
  - Check "Track events and persist to S3" step
- **Post Daily Event Summary**: Runs daily at 6 PM UTC
  - Check logs to see if events were posted

### S3 Bucket

Monitor bucket size and object count:
```bash
aws s3 ls s3://YOUR-BUCKET-NAME/upcoming-history/ --recursive --summarize
```

Note: Old snapshots can be cleaned up periodically. The system only needs:
- `latest.yaml` (most recent)
- `metadata.json` (event tracking)
- Last few timestamped snapshots (for debugging)

Consider setting up S3 lifecycle policy to delete snapshots older than 90 days.

## Troubleshooting

### RSS Feed Shows "not yet available"

**Cause**: S3_BUCKET not configured or no metadata exists yet

**Fix**:
1. Verify S3_BUCKET environment variable is set in app
2. Wait for first deployment to populate S3
3. Check S3 bucket for metadata.json

### Daily Summary Not Posting

**Cause 1**: No events added today

**Fix**: Normal behavior, nothing to do

**Cause 2**: MB_TOKEN not set or invalid

**Fix**: 
1. Verify MB_TOKEN secret is set correctly
2. Get new token from https://micro.blog/account/apps
3. Update GitHub secret

**Cause 3**: AWS credentials not working

**Fix**:
1. Check GitHub Actions workflow logs
2. Verify AWS_ROLE_ARN is correct
3. Check IAM role has required S3 permissions

### Track Events Failing

**Cause**: Missing S3 permissions

**Fix**:
1. Verify CDK stack was redeployed with updated permissions
2. Check IAM role includes s3:GetObject
3. Review CloudWatch logs for detailed error

## Testing Locally

### Test Event Tracking
```bash
export S3_BUCKET=your-bucket
export AWS_PROFILE=your-profile  # or use AWS credentials

python track_events.py --dry-run
```

### Test RSS Feed Generation
```bash
export S3_BUCKET=your-bucket
export AWS_PROFILE=your-profile

python generate_rss_feed.py > test-feed.xml
```

### Test Daily Summary
```bash
export S3_BUCKET=your-bucket
export MB_TOKEN=your-token
export AWS_PROFILE=your-profile

python post_daily_event_summary.py --dry-run
python post_daily_event_summary.py --dry-run --date 2026-02-01
```

## Rollback Plan

If issues arise, you can temporarily disable the features:

1. **Disable event tracking**: Comment out the "Track events" step in `.github/workflows/deploy.yml`
2. **Disable daily summaries**: Disable the workflow in GitHub Actions UI
3. **Remove RSS route**: The RSS feed will show "not yet available" if S3 is not configured

The core site functionality is not affected by these features.
