# Micro.blog Configuration Guide

## Issue: Weekly Events Posted to Wrong Blog

**Problem:** Weekly events posts went to `https://ross.karchner.com` instead of `https://updates.dctech.events/`

**Root Cause:** The GitHub repository variable `MICROBLOG_DESTINATION` was set to the incorrect blog URL.

## Solution (Fixed)

**The default destination is now hardcoded in the scripts!**

All posting scripts now default to `https://updates.dctech.events/` if the `MICROBLOG_DESTINATION` environment variable is not set or is empty.

### What This Means

1. **No action required for correct operation** - Posts will go to the right blog by default
2. **If the variable is set incorrectly**, either:
   - Update it to `https://updates.dctech.events/`, OR
   - Remove it entirely to use the default

### Removing/Updating the GitHub Repository Variable (Optional)

Since the correct default is now in the code, you can either:

**Option 1: Remove the variable** (recommended - simpler)
1. Go to GitHub repository Settings → Secrets and variables → Actions → Repository variables
2. Find `MICROBLOG_DESTINATION`
3. Delete it (posts will use the default)

**Option 2: Update the variable**
1. Go to GitHub repository Settings → Secrets and variables → Actions → Repository variables
2. Find `MICROBLOG_DESTINATION`
3. Update its value to: `https://updates.dctech.events/`

## How Micro.blog Destination Works

All micro.blog posting scripts now default to posting to `https://updates.dctech.events/`:

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

After updating the variable, verify:

- [ ] Variable `MICROBLOG_DESTINATION` is either not set (uses default) OR set to `https://updates.dctech.events/`
- [ ] If variable is set, ensure trailing slash is present: `https://updates.dctech.events/`
- [ ] Test with dry-run mode to see which blog would be posted to
- [ ] Check workflow logs to confirm the correct destination in use
- [ ] Verify actual posts appear at https://updates.dctech.events/

## Common Mistakes to Avoid

1. **Setting wrong URL**: If `MICROBLOG_DESTINATION` is set, it must be `https://updates.dctech.events/` not `ross.karchner.com`
2. **Missing trailing slash**: If set, always use `https://updates.dctech.events/` (with trailing slash)
3. **Using secrets instead of variables**: `MICROBLOG_DESTINATION` is a repository **variable**, not a secret (but it's optional now)
4. **Confusing with MB_TOKEN**: The token (`MB_TOKEN`) is separate from the destination URL

**Note:** Since the default is now correct, the easiest solution is to not set `MICROBLOG_DESTINATION` at all.

## Additional Resources

- Micro.blog documentation: https://help.micro.blog/t/micropub-api/155
- Repository testing checklist: `TESTING_CHECKLIST.md`
- Social media posting documentation: `SOCIAL_MEDIA_POSTING.md`
- Event tracking documentation: `EVENT_TRACKING.md`
