# Event Classification & Tagging System

## Overview

The event classification system automatically categorizes DC Tech Events using AWS Bedrock Claude API. Site curators define a set of tags, and each event is classified based on its title, group name, description, and website content. Results are cached to prevent redundant classifications.

## System Components

### 1. **tags.yaml** - Tag Configuration
Central configuration file where site curators define the taxonomy of event tags. Each tag has:
- `id`: Unique identifier (lowercase, hyphen-separated) - used in URLs and code
- `name`: Display name shown to users
- `description`: Explanation of what events belong in this tag

**Example:**
```yaml
tags:
  - id: ai
    name: AI & Machine Learning
    description: Artificial intelligence, machine learning, deep learning, LLMs, and AI applications
  - id: python
    name: Python
    description: Python programming language, Python libraries, and Python-focused development
```

### 2. **classifier.py** - Classification Engine
Handles event classification using AWS Bedrock Claude 3.5 Sonnet model.

**Key Functions:**
- `load_tags_config()` - Load tags from tags.yaml
- `classify_events(events, skip_cache=False)` - Classify a batch of events
- `classify_event(event, tags)` - Classify a single event using Claude
- `get_event_cache_key(event)` - Generate cache key from event immutable fields

**Caching Strategy:**
- Cache file: `_cache/event_tags_cache.json`
- Cache key based on: event title, group name, and URL (immutable fields)
- Cache invalidated when `tags.yaml` changes (detected via MD5 hash)
- Cache includes hash of current tags configuration to detect curator changes

### 3. **Integration with generate_month_data.py**
Classification runs during YAML generation, which happens:
- During `make build` (static site generation)
- When GitHub Actions workflow runs `refresh_calendars.py`
- Manually when `python generate_month_data.py` is run

**Flow:**
1. All events are collected and deduplicated
2. Events are sorted by date/time
3. **Classification runs** - tags added to each event
4. Events written to `_data/upcoming.yaml` with tags
5. Stats generated

### 4. **Web Interface - app.py**
Provides routes for browsing and filtering by tags:
- `GET /tags/` - Tag directory showing all tags and event counts
- `GET /tags/<tag_id>/` - Events for a specific tag

**Helper Functions:**
- `load_tags_config()` - Load tag definitions
- `filter_events_by_tag(events, tag_id)` - Filter events with specific tag
- `get_tag_info(tag_id)` - Get tag metadata

### 5. **HTML Templates**
- `templates/tags.html` - Tag directory/index page with grid layout
- `templates/tag_page.html` - Individual tag page with event listings

### 6. **Static Site Generation - freeze.py**
Registers URL generators for tag pages so they're built during `make build`:
```python
@freezer.register_generator
def tags_page():
    """Generate the tags index page"""
    yield {}

@freezer.register_generator
def tag_page():
    """Generate URLs for tag pages"""
    tags = load_tags_config()
    for tag in tags:
        yield {'tag_id': tag['id']}
```

## Current Tags

The system launches with these 20 curated tags based on DC Tech event patterns:

1. **AI & Machine Learning** - AI, ML, deep learning, LLMs
2. **Startups & Entrepreneurship** - Co-founder networking, pitch events
3. **Cybersecurity** - Infosec, pentesting, threat analysis
4. **Web Development** - Frontend, backend, full-stack
5. **Python** - Python language and libraries
6. **Rust** - Rust systems programming
7. **Go/Golang** - Golang development
8. **Game Development** - Game engines, indie games
9. **Cloud & DevOps** - AWS, Azure, GCP, infrastructure
10. **Data & Analytics** - Data science, engineering, analytics
11. **Cryptocurrency & Web3** - Blockchain, Web3, NFTs
12. **Design & UX** - User experience, product design
13. **Hardware & IoT** - Hardware, embedded systems
14. **Mobile Development** - iOS, Android, React Native
15. **Accessibility** - Web a11y, inclusive design
16. **Women in Tech** - Women-focused initiatives
17. **Networking & Community** - Social events, mixers
18. **Civic Tech** - Tech for public good
19. **Defense & Government Tech** - Defense tech, federal
20. **Open Source** - Open source communities

## AWS Bedrock Setup

### Prerequisites
1. AWS account with Bedrock access enabled
2. Claude 3.5 Sonnet model available in `us-east-1` region

### IAM Permissions Required
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20241022"
    }
  ]
}
```

### Environment Setup
The classifier uses the default AWS SDK credentials chain:
1. Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`
2. AWS credentials file: `~/.aws/credentials`
3. IAM role (when running on EC2/Lambda)
4. In CI/CD: Use GitHub Actions OIDC or secrets

**GitHub Actions Example:**
```yaml
env:
  AWS_REGION: us-east-1
  AWS_ROLE_TO_ASSUME: arn:aws:iam::ACCOUNT_ID:role/bedrock-classifier
```

### Testing Classification Locally
```bash
# Set AWS credentials
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"

# Run generation with classification
python generate_month_data.py

# View cached results
cat _cache/event_tags_cache.json | python -m json.tool
```

## Usage

### For Site Curators - Updating Tags

**To add or modify tags:**

1. Edit `tags.yaml` - add new tag or modify existing one
2. Run: `python generate_month_data.py`
   - Cache is automatically invalidated
   - All events are re-classified with new tags
3. Verify by checking: `_cache/event_tags_cache.json`

**Example - Adding a new tag:**
```yaml
tags:
  # ... existing tags ...
  - id: blockchain
    name: Blockchain Development
    description: Smart contracts, Ethereum, blockchain infrastructure
```

Then regenerate: `python generate_month_data.py`

### For Developers - Manual Classification

```python
from classifier import classify_events
import yaml

# Load events
with open('_data/upcoming.yaml') as f:
    events = yaml.safe_load(f)

# Classify (uses cache by default)
classified = classify_events(events)

# Force re-classification
classified = classify_events(events, skip_cache=True)

# Check tags on an event
for event in classified:
    print(f"{event['title']}: {event.get('tags', [])}")
```

### For Users - Browsing by Tag

- Visit `/tags/` to see tag directory
- Click any tag to see events in that category
- Tags are also visible in event data via API

### Submitting Events with Tags

When users submit events via the form (`/submit/`), they can optionally:
- Select tags that apply to their event
- These user-selected tags are stored with the event
- During classification, Claude combines user tags + auto-detected tags

## How Classification Works

### The Claude Prompt

The classifier sends this system to Claude 3.5 Sonnet:

```
You are an event classifier. Classify the following event with ONLY the tags that clearly apply.

Available tags:
- ai: Artificial intelligence, machine learning, deep learning, LLMs, and AI applications
- startups: Startup communities, co-founder networking, pitch events, and entrepreneurship workshops
... (all tags listed)

Event to classify:
Title: [event title]
Group: [organizing group]
Description: [event description]
URL: [event website]

Return ONLY a JSON array of tag IDs that apply to this event, nothing else.
Example: ["ai", "startups"]
If no tags apply, return an empty array: []

Your response:
```

Claude responds with valid JSON like: `["ai", "python", "startups"]`

### Cache Invalidation

The cache is automatically invalidated when:
1. Tags in `tags.yaml` are added, removed, or modified
2. Tag descriptions change (tags are compared via MD5 hash)
3. Event is not found in cache (new event)

**Manual cache clearing:**
```bash
rm _cache/event_tags_cache.json
python generate_month_data.py  # Rebuilds cache
```

## Performance & Costs

### Classification Costs
- **Per event**: ~1-2 cents USD with Claude 3.5 Sonnet
- **Efficiency**: Cache prevents re-classification
- **Example**: 100 new events = ~$1-2 cost

### Performance
- **First run**: ~100 events takes ~30-60 seconds (API rate limiting)
- **Subsequent runs**: ~0.1 seconds (all cached)
- **Tag change**: Full re-classification takes 30-60 seconds

### Optimization Strategies
1. **Batch classification** - Handled automatically by `classify_events()`
2. **Caching** - Only new/modified events are classified
3. **Rate limiting** - AWS handles this transparently
4. **Error handling** - Classification failures don't break the build

## Data Structure

### Events with Tags (in upcoming.yaml)

```yaml
- title: "AI In Hyperconverged Infrastructure"
  group: "AI Innovators Network"
  description: "Meetup exploring AI in Hyperconverged Infrastructure..."
  url: https://www.meetup.com/...
  date: '2026-01-07'
  time: '18:00'
  location: "Arlington, VA"
  tags:
    - ai
    - cloud
    - hardware
```

### Cache Structure (_cache/event_tags_cache.json)

```json
{
  "tags_hash": "a1b2c3d4e5f6...",
  "events": {
    "event-cache-key-hash": ["ai", "cloud"],
    "another-event-hash": ["python", "web-dev"],
    ...
  }
}
```

## Integration with Event Submission

Users can tag events when submitting via the form. The event submission form (`templates/submit.html`) includes:
- Multi-select dropdown for available tags
- User-selected tags stored in the event
- During classification, user tags + auto-detected tags are merged

## Troubleshooting

### Classification Not Running
```bash
# Check if AWS credentials are set
echo $AWS_ACCESS_KEY_ID

# Check cache
ls -la _cache/event_tags_cache.json

# Check logs during generation
python generate_month_data.py 2>&1 | grep -i classify
```

### Events Not Tagged
1. Check `_data/upcoming.yaml` has `tags:` field
2. Verify AWS Bedrock permissions
3. Check CloudWatch logs for Bedrock invocations
4. Try: `python classifier.py` directly with test events

### Cache Issues
```bash
# Clear cache completely
rm _cache/event_tags_cache.json

# Regenerate with full re-classification
python generate_month_data.py
```

### Bedrock API Errors
Common errors:
- **ThrottlingException**: Rate limiting, retry later
- **AccessDeniedException**: Missing IAM permissions
- **ValidationException**: Model not available in region

## Future Enhancements

Potential improvements:
1. Multi-tag prediction confidence scores
2. Tag suggestions in event submission form
3. Tag-based calendar filters (UI)
4. Tag analytics and trending topics
5. Alternative classifiers (custom ML models, keyword matching)
6. User feedback loop for classification accuracy

## Files Changed/Added

### New Files
- `tags.yaml` - Tag configuration
- `classifier.py` - Classification engine
- `templates/tags.html` - Tag directory template
- `templates/tag_page.html` - Individual tag page template

### Modified Files
- `generate_month_data.py` - Added classification step
- `app.py` - Added tag routes and helper functions
- `freeze.py` - Added tag page generators
- `requirements.txt` - Added boto3 dependency

### Cache Files
- `_cache/event_tags_cache.json` - Auto-created during generation

## References

- **AWS Bedrock**: https://docs.aws.amazon.com/bedrock/
- **Claude API**: https://docs.anthropic.com/en/api/messages
- **Repository**: https://github.com/DCTE/dctech.events
