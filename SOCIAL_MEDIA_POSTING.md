# Social Media Posting Scripts Documentation

## Current Implementation (2026)

### Daily Posts to Micro.blog

The primary social media posting is now done via **`post_todays_events_to_microblog.py`**, which posts a daily summary of today's events to micro.blog.

**Script:** `post_todays_events_to_microblog.py`

**Features:**
- Posts text-only content (no title) to micro.blog via Micropub
- Keeps posts under 300 characters
- Uses two format preferences (in order):
  1. Full list: "DC Tech Events today: Event1, Event2, Event3  [URL]"
  2. Truncated: "DC Tech Events today: Event1, Event2, and 3 more  [URL]"
- Only posts in-person events (virtual events are filtered out)
- Links to the weekly calendar page with date anchor

**Environment Variables Required:**
- `MB_TOKEN`: Micro.blog app token (from Account → App tokens)
- ~~`MICROBLOG_DESTINATION`~~: **No longer used** - defaults to `https://updates.dctech.events/` (hardcoded in script)

**Usage:**
```bash
# Post today's events
python post_todays_events_to_microblog.py

# Test without posting (dry run)
python post_todays_events_to_microblog.py --dry-run

# Post events for a specific date
python post_todays_events_to_microblog.py --date 2026-02-06
```

**Automated Posting:**
The `.github/workflows/social-media-posts.yml` workflow runs daily at 8 AM Eastern (12:00 UTC) to automatically post today's events.

**Example Post:**
```
DC Tech Events today: Python Meetup, JavaScript Workshop, Ruby Social  https://dctech.events/week/2026-W06/#2026-02-06
```

---

## Legacy Scripts (Mastodon and Bluesky)

This document provides a detailed explanation of the legacy Mastodon and Bluesky posting scripts, which are still available but no longer used in the automated daily workflow.

### Overview

Two legacy scripts are available for posting daily event summaries to social media:

1. **`post_to_mastodon.py`** - Posts to Mastodon using ActivityPub
2. **`post_to_bluesky.py`** - Posts to Bluesky using AT Protocol

Both scripts:
- Only post if there are events scheduled for the target day
- Support dry-run mode for testing
- Can post for a specific date or default to today
- Format events with time and title information
- Include a link back to the main website

## Script 1: post_to_mastodon.py

### Protocol: ActivityPub

Mastodon implements the **ActivityPub** protocol, which is a W3C Recommendation for decentralized social networking.

#### ActivityPub Standards Used

1. **ActivityPub (W3C Recommendation)**
   - Decentralized social networking protocol
   - Enables federation between different Mastodon instances and compatible services
   - Server-to-server (S2S) and client-to-server (C2S) protocol

2. **ActivityStreams 2.0**
   - JSON-based format for representing social activities and objects
   - Posts (called "statuses" or "notes") are Activity objects
   - Follows a vocabulary of activity types (Create, Update, Delete, etc.)

3. **OAuth 2.0**
   - Industry-standard authorization framework
   - Used for authenticating API requests
   - Access tokens are bearer tokens in HTTP Authorization header

4. **HTTP Signatures**
   - Used for server-to-server authentication (handled automatically by Mastodon)
   - Cryptographic signatures verify the authenticity of federated messages

### Mastodon API Details

**Authentication:**
```
Authorization: Bearer <access_token>
```

**API Endpoint:**
```
POST /api/v1/statuses
```

**Request Format:**
```json
{
  "status": "Post text content here",
  "visibility": "public"
}
```

**Response Format (ActivityStreams object):**
```json
{
  "id": "109347820124984227",
  "created_at": "2026-01-05T12:00:00.000Z",
  "url": "https://mastodon.social/@username/109347820124984227",
  "content": "<p>Post text content here</p>",
  ...
}
```

### Character Limit

- **500 characters** (default, varies by instance)
- Scripts use conservative estimate of 500

### Environment Variables

```bash
export MASTODON_ACCESS_TOKEN="your-access-token"
export MASTODON_INSTANCE_URL="https://mastodon.social"
```

**Getting an Access Token:**
1. Log into your Mastodon account
2. Go to Settings → Development → New Application
3. Give it a name (e.g., "DC Tech Events Bot")
4. Select scopes (at minimum: `write:statuses`)
5. Copy the access token

### Usage Examples

```bash
# Post today's events
python post_to_mastodon.py

# Test without posting (dry run)
python post_to_mastodon.py --dry-run

# Post events for a specific date
python post_to_mastodon.py --date 2026-01-15
```

### Example Output

For a day with 3 events, the script might post:

```
📅 Tech events happening today (January 5):

• 6:30pm - Python User Group Meetup
• 7:00pm - Cloud Native DC
• All Day - AWS re:Invent Watch Party

More info: https://dctech.events
```

---

## Script 2: post_to_bluesky.py

### Protocol: AT Protocol (Authenticated Transfer Protocol)

Bluesky uses the **AT Protocol**, a newer federated social networking protocol designed for decentralized identity and content.

#### AT Protocol Standards Used

1. **AT Protocol (atproto)**
   - Authenticated Transfer Protocol for federated social networking
   - Personal Data Repositories (PDRs) store user data
   - Account portability across different hosting providers
   - Decentralized identity and content addressing

2. **XRPC (Cross-organization RPC)**
   - RPC protocol used for all AT Protocol API calls
   - HTTP-based with JSON payloads
   - Endpoints are namespaced by reverse-domain notation
   - Example: `com.atproto.server.createSession`

3. **Lexicons**
   - Schema definitions for data structures and API methods
   - Similar to OpenAPI/Swagger but AT Protocol-specific
   - Ensures type safety and compatibility
   - Example lexicon: `app.bsky.feed.post`

4. **DIDs (Decentralized Identifiers)**
   - W3C standard for decentralized digital identity
   - Two types supported: `did:plc:` and `did:web:`
   - Used to identify users' Personal Data Repositories
   - Example: `did:plc:z72i7hdynmk6r22z27h6tvur`

5. **Content Addressing (CID)**
   - Content Identifiers using IPFS-style addressing
   - Each post/record gets a unique CID
   - Enables cryptographic verification of content

### Bluesky/AT Protocol API Details

**Authentication (Session Creation):**
```
POST /xrpc/com.atproto.server.createSession
```
```json
{
  "identifier": "username.bsky.social",
  "password": "app-password"
}
```

**Response:**
```json
{
  "accessJwt": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refreshJwt": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "handle": "username.bsky.social",
  "did": "did:plc:z72i7hdynmk6r22z27h6tvur"
}
```

**Creating a Post:**
```
POST /xrpc/com.atproto.repo.createRecord
Authorization: Bearer <accessJwt>
```
```json
{
  "repo": "did:plc:z72i7hdynmk6r22z27h6tvur",
  "collection": "app.bsky.feed.post",
  "record": {
    "$type": "app.bsky.feed.post",
    "text": "Post content here",
    "createdAt": "2026-01-05T12:00:00.000Z"
  }
}
```

**Response:**
```json
{
  "uri": "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.post/3kb42z3...",
  "cid": "bafyreih4fgtabqerf5r4z..."
}
```

### Character Limit

- **300 characters** (grapheme count, not bytes)
- Significantly shorter than Mastodon
- Scripts format posts more concisely

### Environment Variables

```bash
export BLUESKY_HANDLE="username.bsky.social"
export BLUESKY_APP_PASSWORD="your-app-password"
```

**Getting an App Password:**
1. Log into your Bluesky account
2. Go to Settings → App Passwords
3. Click "Add App Password"
4. Give it a name (e.g., "DC Tech Events Bot")
5. Copy the generated password (not your main password!)

### Usage Examples

```bash
# Post today's events
python post_to_bluesky.py

# Test without posting (dry run)
python post_to_bluesky.py --dry-run

# Post events for a specific date
python post_to_bluesky.py --date 2026-01-15
```

### Example Output

For the same day with 3 events, Bluesky post would be shorter:

```
📅 DC tech events today (Jan 5):

• 6:30pm - Python User Group
• 7:00pm - Cloud Native DC
• All Day - AWS re:Invent...

https://dctech.events
```

---

## Key Differences Between Scripts

### 1. **Protocol Architecture**

**Mastodon (ActivityPub):**
- Built on existing web standards (ActivityStreams, WebFinger, HTTP Signatures)
- Instance-based federation (each instance is a separate community)
- Follows a client-server model similar to email
- Server-to-server communication uses push model (activities are pushed to followers' servers)

**Bluesky (AT Protocol):**
- Purpose-built protocol for decentralized social networking
- Account-based identity (users own their identity via DIDs)
- Personal Data Repositories act as user-controlled data stores
- Relay/indexing model allows different views of the same data (App Views)
- Built for account portability (can move between providers)

### 2. **Authentication**

**Mastodon:**
- OAuth 2.0 with long-lived access tokens
- One token creation step, then reusable
- Token scoped to specific instance

**Bluesky:**
- App passwords with JWT-based sessions
- Must create session each time (short-lived JWT)
- Returns both access and refresh tokens
- DID-based identity separate from hosting provider

### 3. **Post Format**

**Mastodon:**
- Posts are Activity objects in ActivityStreams format
- Server converts plain text to HTML with `<p>` tags
- Supports Markdown-like formatting
- Returns a URL to view the post

**Bluesky:**
- Posts are records in a lexicon-defined schema
- Stored in user's Personal Data Repository
- Plain text only (no HTML conversion)
- Returns AT URI and CID (content identifier)

### 4. **Character Limits**

**Mastodon:** 500 characters
- More space for event details
- Can show more events per post
- Longer event titles

**Bluesky:** 300 characters  
- More concise posts required
- Fewer events shown per post
- Event titles may be truncated more aggressively

### 5. **Post Output Differences**

**Mastodon posts:**
- Typically show 8-10 events
- Full date format: "January 5, 2026"
- More breathing room in formatting
- URL at the end with "More info:" label

**Bluesky posts:**
- Typically show 5-8 events
- Abbreviated date: "Jan 5"
- Tighter formatting to fit character limit
- URL at the end without label
- More aggressive title truncation

### 6. **Visibility & Federation**

**Mastodon:**
- Posts federate to followers on other instances via ActivityPub
- Appears in public timeline and federated timeline
- Can be boosted (retweeted) to reach wider audience
- Search is limited (by design for privacy)

**Bluesky:**
- Posts visible to all followers immediately
- Indexed by relays for discoverability
- Can be reposted to reach wider audience
- Full-text search available across network
- Different "App Views" can show same content differently

### 7. **Data Ownership**

**Mastodon:**
- Content owned by user but stored on instance server
- Export available, but moving between instances requires followers to re-follow
- Instance administrator has control over data storage

**Bluesky:**
- User owns their data via Personal Data Repository
- Account portability: can move between providers with same identity
- DID-based identity persists across moves
- Content addressable via CID ensures data integrity

---

## Automated Posting with GitHub Actions

This repository includes a GitHub Actions workflow that automatically posts daily event summaries at 8am EST.

### Setup

The workflow is located at `.github/workflows/social-media-posts.yml` and requires the following secrets to be configured in your GitHub repository:

1. Go to your repository Settings → Secrets and variables → Actions
2. Add the following secrets:
   - `MASTODON_ACCESS_TOKEN` - Your Mastodon OAuth token
   - `MASTODON_INSTANCE_URL` - Your Mastodon instance URL (e.g., `https://mastodon.social`)
   - `BLUESKY_HANDLE` - Your Bluesky handle (e.g., `username.bsky.social`)
   - `BLUESKY_APP_PASSWORD` - Your Bluesky app password

### Workflow Features

- **Scheduled posting**: Runs daily at 8am EST (12:00 UTC)
- **Manual triggering**: Can be triggered manually with optional custom date
- **Error resilience**: Continues even if one platform fails (`continue-on-error`)
- **Fresh data**: Generates event data before posting

### Manual Triggering

To manually trigger the workflow:

1. Go to Actions tab in your GitHub repository
2. Select "Daily Social Media Posts" workflow
3. Click "Run workflow"
4. Optionally specify a custom date (YYYY-MM-DD format)

---

## Scheduling Daily Posts (Alternative Methods)

### Example Cron Job

```cron
# Post to Mastodon daily at 8 AM Eastern
0 8 * * * cd /path/to/dctech.events && /usr/bin/python3 post_to_mastodon.py

# Post to Bluesky daily at 8:05 AM Eastern
5 8 * * * cd /path/to/dctech.events && /usr/bin/python3 post_to_bluesky.py
```

### Example Custom GitHub Actions Workflow

```yaml
name: Daily Social Media Posts

on:
  schedule:
    - cron: '0 13 * * *'  # 8 AM Eastern (UTC-5) = 13:00 UTC
  workflow_dispatch:  # Allow manual trigger

jobs:
  post-to-social:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Build event data
        run: |
          make generate-month-data
      
      - name: Post to Mastodon
        env:
          MASTODON_ACCESS_TOKEN: ${{ secrets.MASTODON_ACCESS_TOKEN }}
          MASTODON_INSTANCE_URL: ${{ secrets.MASTODON_INSTANCE_URL }}
        run: python post_to_mastodon.py
      
      - name: Post to Bluesky
        env:
          BLUESKY_HANDLE: ${{ secrets.BLUESKY_HANDLE }}
          BLUESKY_APP_PASSWORD: ${{ secrets.BLUESKY_APP_PASSWORD }}
        run: python post_to_bluesky.py
```

---

## Testing

Both scripts support `--dry-run` mode for safe testing:

```bash
# Test Mastodon post
python post_to_mastodon.py --dry-run

# Test Bluesky post
python post_to_bluesky.py --dry-run
```

This will show you exactly what would be posted without actually posting to the social networks.

---

## Error Handling

Both scripts:
- Exit with code 0 if successful or if no events exist
- Exit with code 1 if there's an error
- Print detailed error messages for debugging
- Handle network timeouts (30 seconds)
- Validate environment variables before attempting to post

Common errors:
- Missing environment variables
- Invalid credentials
- Network connectivity issues
- API rate limits (if posting too frequently)
- Character limit exceeded (text truncated automatically)

---

## Dependencies

Both scripts require the following Python packages (already in requirements.txt):
- `pyyaml` - For reading event data
- `pytz` - For timezone handling
- `requests` - For HTTP API calls

No additional dependencies are needed.

---

## Summary

Both scripts provide similar functionality but use fundamentally different protocols:

- **Mastodon** uses the mature, W3C-standardized ActivityPub protocol with instance-based federation
- **Bluesky** uses the newer AT Protocol with DIDs, personal data repositories, and account portability

The main practical differences users will notice:
1. **Post length**: Mastodon allows longer posts (500 vs 300 chars)
2. **Setup**: Different authentication mechanisms (OAuth token vs app password)
3. **Output format**: Bluesky posts are more concise due to character limits
4. **Federation model**: ActivityPub (push) vs AT Protocol (relay/indexing)

Both scripts are production-ready and can be safely deployed for daily automated posting.
