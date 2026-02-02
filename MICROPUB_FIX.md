# Micropub Implementation Fix

## Problem
PR #217 attempted to fix Micropub posting errors by converting from form-encoded to JSON format, but posts were still failing with HTTP 500 errors from micro.blog.

## Root Cause
The W3C Micropub specification (https://www.w3.org/TR/micropub/) requires that HTML content be sent as an **object with an 'html' key**, not as a plain string.

### Incorrect (what PR #217 did):
```json
{
  "type": ["h-entry"],
  "properties": {
    "name": ["Post Title"],
    "content": ["<p>HTML content here</p>"]
  }
}
```

### Correct (per W3C Micropub spec section 3.3.2):
```json
{
  "type": ["h-entry"],
  "properties": {
    "name": ["Post Title"],
    "content": [{"html": "<p>HTML content here</p>"}]
  }
}
```

## Solution
Updated both files that post to micro.blog:

1. **post_newsletter_to_microblog.py**
   - Changed `'content': [content]` to `'content': [{'html': content}]`

2. **post_daily_event_summary.py**
   - Converted from form-encoded format to JSON format
   - Applied same fix: `'content': [{'html': content}]`

## Testing
- Created comprehensive tests in `test_newsletter_micropub.py`
- Updated existing tests in `test_event_tracking.py`
- All tests passing
- Dry-run tests confirm correct JSON structure

## References
- W3C Micropub Specification: https://www.w3.org/TR/micropub/
- Section 3.3.2: JSON Syntax for HTML content
- Microformats2 documentation: https://microformats.org/wiki/microformats2
