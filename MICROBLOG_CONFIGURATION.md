# Micro.blog Configuration Guide

## Issue: Weekly Events Posted to Wrong Blog

**Problem:** Weekly events posts went to `https://ross.karchner.com` instead of `https://updates.dctech.events/`

**Root Cause:** The GitHub repository variable `MICROBLOG_DESTINATION` was set to the incorrect blog URL.

## Solution (Fixed)

**The workflows no longer use the GitHub repository variable!**

As of February 2026, all GitHub Actions workflows have been updated to NOT pass the `MICROBLOG_DESTINATION` environment variable to the posting scripts. The scripts now always use their built-in default of `https://updates.dctech.events/`.

### What This Means

1. **No configuration required** - Posts will always go to the right blog
2. **The GitHub variable has no effect** - Even if set, it won't be used by the workflows
3. **Simpler and more reliable** - No risk of misconfiguration

### GitHub Repository Variable (No Longer Used)

The `MICROBLOG_DESTINATION` GitHub repository variable is **no longer used** by the workflows. You can safely delete it from the repository settings if it exists.

To remove it:
1. Go to GitHub repository Settings → Secrets and variables → Actions → Repository variables
2. Find `MICROBLOG_DESTINATION`
3. Delete it (optional - it's ignored anyway)

## How Micro.blog Destination Works

All micro.blog posting scripts now default to posting to `https://updates.dctech.events/`:

- `post_newsletter_to_microblog.py` - Weekly newsletter posts (Mondays at 7 AM ET)
- `post_daily_event_summary.py` - Daily summaries of new events (11 PM UTC)
- `post_todays_events_to_microblog.py` - Today's events posts (8 AM ET)

### GitHub Actions Workflows

Three workflows post to micro.blog:

1. `.github/workflows/post-newsletter-microblog.yml` - Weekly newsletter
2. `.github/workflows/post-daily-event-summary.yml` - Daily summaries
3. `.github/workflows/social-media-posts.yml` - Today's events

**As of February 2026:** These workflows no longer pass the `MICROBLOG_DESTINATION` environment variable. The scripts always use their built-in default of `https://updates.dctech.events/`.

### Environment Variable in Scripts

All scripts now default to the correct destination:
```python
# Default to updates.dctech.events if not specified
MICROBLOG_DESTINATION = os.environ.get('MICROBLOG_DESTINATION', 'https://updates.dctech.events/')
```

This is always passed to the Micropub API as the `mp-destination` parameter:
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

To test locally (the default destination will be used):

```bash
export MB_TOKEN="your-token-here"
# MICROBLOG_DESTINATION is optional - defaults to https://updates.dctech.events/

# Test newsletter post (dry run)
python post_newsletter_to_microblog.py --dry-run

# Test daily summary (dry run)
python post_daily_event_summary.py --dry-run

# Test today's events (dry run)
python post_todays_events_to_microblog.py --dry-run
```

### Manual Workflow Testing

To test via GitHub Actions with manual workflow dispatch:

1. Go to **Actions** tab in GitHub
2. Select the workflow to test (e.g., "Post Weekly Newsletter to Micro.blog")
3. Click **Run workflow**
4. Select the **dry_run** option (if available)
5. Run and check the logs to verify the destination URL is correct

## Verification Checklist

After the fix, verify:

- [x] Workflows no longer pass `MICROBLOG_DESTINATION` environment variable
- [ ] Test with dry-run mode to confirm destination is `https://updates.dctech.events/`
- [ ] Check workflow logs to confirm the correct destination in use
- [ ] Verify actual posts appear at https://updates.dctech.events/

## Common Mistakes to Avoid (Historical)

These issues are no longer possible since the workflows don't use the variable:

1. ~~**Setting wrong URL**~~ - Variable is no longer used
2. ~~**Missing trailing slash**~~ - Variable is no longer used
3. ~~**Using secrets instead of variables**~~ - Variable is no longer used
4. **MB_TOKEN must be a secret**: The token (`MB_TOKEN`) is still required as a repository **secret**

**Note:** The workflows are now simpler and more reliable since they don't depend on repository variable configuration.

## Additional Resources

- Micro.blog documentation: https://help.micro.blog/t/micropub-api/155
- Repository testing checklist: `TESTING_CHECKLIST.md`
- Social media posting documentation: `SOCIAL_MEDIA_POSTING.md`
- Event tracking documentation: `EVENT_TRACKING.md`
