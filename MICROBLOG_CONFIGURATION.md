# Micro.blog Configuration Guide

## Issue: Weekly Events Posted to Wrong Blog

**Problem:** Weekly events posts went to `https://ross.karchner.com` instead of `https://updates.dctech.events/`

**Root Cause:** The GitHub repository variable `MICROBLOG_DESTINATION` was set to the incorrect blog URL.

## Solution

### Update GitHub Repository Variable

The `MICROBLOG_DESTINATION` variable must be set to `https://updates.dctech.events/`

**Steps to fix:**

1. Go to GitHub repository: https://github.com/rosskarchner/dctech.events
2. Navigate to **Settings** → **Secrets and variables** → **Actions** → **Repository variables**
3. Find the variable named `MICROBLOG_DESTINATION`
4. Update its value to: `https://updates.dctech.events/`
5. Save the change

## How Micro.blog Destination Works

All micro.blog posting scripts in this repository use the `MICROBLOG_DESTINATION` environment variable to specify which blog to post to:

- `post_newsletter_to_microblog.py` - Weekly newsletter posts (Mondays at 7 AM ET)
- `post_daily_event_summary.py` - Daily summaries of new events (11 PM UTC)
- `post_todays_events_to_microblog.py` - Today's events posts (8 AM ET)

### GitHub Actions Workflows

Three workflows use this variable:

1. `.github/workflows/post-newsletter-microblog.yml` - Weekly newsletter
2. `.github/workflows/post-daily-event-summary.yml` - Daily summaries
3. `.github/workflows/social-media-posts.yml` - Today's events

Each workflow reads the variable as: `MICROBLOG_DESTINATION: ${{ vars.MICROBLOG_DESTINATION }}`

### Environment Variable in Scripts

All scripts check for the environment variable:
```python
MICROBLOG_DESTINATION = os.environ.get('MICROBLOG_DESTINATION')
```

If set, this is passed to the Micropub API as the `mp-destination` parameter:
```python
data = {
    'h': 'entry',
    'content': content,
}
if destination:
    data['mp-destination'] = destination
```

## Testing the Configuration

### Local Testing

To test locally with the correct destination:

```bash
export MB_TOKEN="your-token-here"
export MICROBLOG_DESTINATION="https://updates.dctech.events/"

# Test newsletter post (dry run)
python post_newsletter_to_microblog.py --dry-run

# Test daily summary (dry run)
python post_daily_event_summary.py --dry-run

# Test today's events (dry run)
python post_todays_events_to_microblog.py --dry-run
```

### Manual Workflow Testing

After updating the repository variable, test with manual workflow dispatch:

1. Go to **Actions** tab in GitHub
2. Select the workflow to test (e.g., "Post Weekly Newsletter to Micro.blog")
3. Click **Run workflow**
4. Select the **dry_run** option (if available)
5. Run and check the logs to verify the destination URL is correct

## Verification Checklist

After updating the variable, verify:

- [ ] Variable `MICROBLOG_DESTINATION` is set to `https://updates.dctech.events/`
- [ ] No trailing slashes inconsistencies (both the variable and code use trailing slash)
- [ ] Test with dry-run mode to see which blog would be posted to
- [ ] Check workflow logs to confirm the correct destination in use
- [ ] Verify actual posts appear at https://updates.dctech.events/

## Common Mistakes to Avoid

1. **Missing trailing slash**: Always use `https://updates.dctech.events/` (with trailing slash)
2. **Wrong domain**: Should be `updates.dctech.events` not `ross.karchner.com`
3. **Using secrets instead of variables**: `MICROBLOG_DESTINATION` is a repository **variable**, not a secret
4. **Confusing with MB_TOKEN**: The token (`MB_TOKEN`) is separate from the destination URL

## Additional Resources

- Micro.blog documentation: https://help.micro.blog/t/micropub-api/155
- Repository testing checklist: `TESTING_CHECKLIST.md`
- Social media posting documentation: `SOCIAL_MEDIA_POSTING.md`
- Event tracking documentation: `EVENT_TRACKING.md`
