# Quick Reference: Social Media Posting Scripts

## Files Added

1. **post_to_mastodon.py** - Mastodon posting script (317 lines)
2. **post_to_bluesky.py** - Bluesky posting script (387 lines)  
3. **SOCIAL_MEDIA_POSTING.md** - Comprehensive documentation (476 lines)
4. **test_social_posting.py** - Unit tests (294 lines, 18 tests)

## Usage

### Mastodon
```bash
# Set credentials
export MASTODON_ACCESS_TOKEN="your-token"
export MASTODON_INSTANCE_URL="https://mastodon.social"

# Post today's events
python post_to_mastodon.py

# Test without posting
python post_to_mastodon.py --dry-run

# Post for specific date
python post_to_mastodon.py --date 2026-01-15
```

### Bluesky
```bash
# Set credentials
export BLUESKY_HANDLE="username.bsky.social"
export BLUESKY_APP_PASSWORD="your-app-password"

# Post today's events
python post_to_bluesky.py

# Test without posting
python post_to_bluesky.py --dry-run

# Post for specific date
python post_to_bluesky.py --date 2026-01-15
```

## How They Work

Both scripts:
1. Load events from `_data/upcoming.yaml`
2. Filter events for the target date (today by default)
3. Exit gracefully if no events exist (exit code 0)
4. Format events with time and title
5. Create platform-specific post text
6. Post to the social network (or show dry-run preview)

## Protocol Details

### Mastodon (ActivityPub)
- **Protocol**: ActivityPub (W3C Recommendation)
- **Auth**: OAuth 2.0 bearer token
- **Endpoint**: `POST /api/v1/statuses`
- **Char Limit**: 500 characters
- **Format**: ActivityStreams JSON

### Bluesky (AT Protocol)
- **Protocol**: AT Protocol (Authenticated Transfer Protocol)
- **Auth**: App password → JWT session
- **Endpoint**: `POST /xrpc/com.atproto.repo.createRecord`
- **Char Limit**: 300 characters
- **Format**: Lexicon-defined records with DIDs

## Key Differences

| Feature | Mastodon | Bluesky |
|---------|----------|---------|
| Character Limit | 500 | 300 |
| Date Format | "January 15" | "Jan 15" |
| Events Shown | 8-10 | 5-8 |
| Protocol | ActivityPub | AT Protocol |
| Identity | Instance-based | DID-based |

## Example Output

### Mastodon
```
📅 Tech events happening today (January 5):

• 6:30pm - Python User Group Meetup
• 7:00pm - Cloud Native DC
• All Day - AWS re:Invent Watch Party

More info: https://dctech.events
```

### Bluesky
```
📅 DC tech events today (Jan 5):

• 6:30pm - Python User Group
• 7:00pm - Cloud Native DC
• All Day - AWS re:Invent...

https://dctech.events
```

## Automation

### GitHub Actions (Included)
The repository includes `.github/workflows/social-media-posts.yml` that:
- Runs daily at 8am EST (12:00 UTC)
- Can be manually triggered with custom dates
- Requires secrets: `MASTODON_ACCESS_TOKEN`, `MASTODON_INSTANCE_URL`, `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD`

To use:
1. Add secrets in GitHub repository Settings → Secrets and variables → Actions
2. Workflow runs automatically every day
3. Manual trigger: Actions tab → "Daily Social Media Posts" → Run workflow

### Alternative: Cron
```cron
# Daily at 8 AM Eastern
0 8 * * * cd /path/to/repo && python post_to_mastodon.py
5 8 * * * cd /path/to/repo && python post_to_bluesky.py
```

For detailed GitHub Actions setup, see `SOCIAL_MEDIA_POSTING.md`.

## Testing

Run the test suite:
```bash
python -m unittest test_social_posting -v
```

All 18 tests cover:
- Event filtering (single day, multi-day, no events)
- Event formatting (with time, without time, truncation)
- Post creation (structure, length limits)
- Edge cases (empty lists, special characters, malformed data)

## Dependencies

All required packages already in `requirements.txt`:
- pyyaml
- pytz
- requests

No additional dependencies needed.

## Security

- ✅ 0 vulnerabilities found in CodeQL scan
- ✅ Environment variables for credentials (not hardcoded)
- ✅ HTTPS for all API calls
- ✅ 30-second timeout on requests
- ✅ Input validation for dates and events

## Production Ready

Both scripts are production-ready and can be:
- Scheduled via cron
- Run in GitHub Actions
- Deployed to CI/CD pipelines
- Used with environment variables from secrets management

For detailed information, see `SOCIAL_MEDIA_POSTING.md`.
