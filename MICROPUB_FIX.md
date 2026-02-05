# Micropub Implementation Fix

## Problem
The weekly newsletter post was failing with HTTP 500 because it sent the entire newsletter HTML (129,365 characters) as the Micropub body. micro.blog can't handle this payload size.

Both scripts were also using JSON Micropub format, but micro.blog only documents form-encoded format.

## Solution

### Weekly newsletter (`post_newsletter_to_microblog.py`)
Rewritten to post a short plain-text **note** (no title) with a link to the weekly page:

```
DC Tech Events for the week of 2/3/26: https://dctech.events/week/2026-W06/
```

- No HTML fetching or parsing — computes the week URL from the current date
- Uses form-encoded Micropub: `h=entry&content=...&mp-destination=...`
- No `name` field → micro.blog treats it as a "note" rather than an "article"
- `beautifulsoup4` dependency removed

### Daily event summary (`post_daily_event_summary.py`)
Switched `post_to_microblog()` from JSON to form-encoded Micropub:

- `h=entry`
- `name=<title>`
- `content=<html content>` (HTML passed directly in content field, not content[html])
- `mp-destination=<url>` as a top-level form parameter

**Note**: While the Micropub spec supports `content[html]`, micro.blog appears to have better compatibility when HTML is passed directly in the `content` field, even when posting articles (with a `name` field).

The rest of the script (S3 reads, event filtering, HTML generation) is unchanged.

## Form-encoded Micropub format

```
POST /micropub HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/x-www-form-urlencoded

h=entry&content=Hello+world&mp-destination=https://updates.dctech.events/
```

**For HTML content**: While the Micropub spec defines `content[html]` for HTML content, micro.blog has better compatibility when HTML is passed directly in the `content` field:

```
h=entry&name=Article+Title&content=<p>HTML+here</p>&mp-destination=https://updates.dctech.events/
```

## Testing
```bash
python -m pytest test_newsletter_micropub.py test_event_tracking.py -v
MB_TOKEN=fake python post_newsletter_to_microblog.py --dry-run
```
