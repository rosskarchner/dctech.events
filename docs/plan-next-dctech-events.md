# Implementation Plan: Dynamic HTMX-Powered next.dctech.events

## Executive Summary

Build a dynamic HTMX-powered iCal aggregator at **next.dctech.events** by extending the existing organize.dctech.events CDK infrastructure. This approach:
- Reuses Cognito User Pool, DynamoDB tables, API Gateway, and Lambda
- Replaces GitHub OAuth with Cognito authentication
- Uses Handlebars.js (canonical Mustache implementation) for templating
- Keeps Python for iCal aggregation (minimal changes)
- Preserves all 110+ group configurations and event aggregation logic
- **Runs in parallel with dctech.events indefinitely** during ongoing migration
- Aggregator continuously syncs new/updated groups and events from GitHub repo

**Timeline**: 4-6 weeks to launch; ongoing maintenance for dual-site operation

**Deployment**: next.dctech.events (cutover to dctech.events planned separately)

---

## Phase 1: Infrastructure Foundation (Week 1-2)

### 1.1 Update CDK Stack (`infrastructure/lib/infrastructure-stack.ts`)

**Add next.dctech.events Certificate & CloudFront Distribution:**

```typescript
// Add ACM certificate for next.dctech.events (us-east-1 required for CloudFront)
const nextDctechCertificate = new certificatemanager.Certificate(this, 'NextDcTechCertificate', {
  domainName: 'next.dctech.events',
  validation: certificatemanager.CertificateValidation.fromDns(hostedZone),
  region: 'us-east-1', // CloudFront requirement
});

// Add CloudFront distribution for next.dctech.events (routes to same Lambda as organize)
const nextDctechDistribution = new cloudfront.Distribution(this, 'NextDcTechDistribution', {
  defaultBehavior: {
    origin: new origins.HttpOrigin(`${api.restApiId}.execute-api.${this.region}.amazonaws.com`, {
      originPath: '/prod', // API Gateway stage
      customHeaders: {
        'X-Site': 'next', // Identifies site to Lambda (dctech or next)
      },
    }),
    viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
    allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
    cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
  },
  additionalBehaviors: {
    '/static/*': {
      origin: new origins.S3Origin(websiteBucket, { originAccessIdentity }),
      viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
    },
  },
  domainNames: ['next.dctech.events'],
  certificate: nextDctechCertificate,
});

// Add Route 53 A & AAAA records for next subdomain
new route53.ARecord(this, 'NextDcTechARecord', {
  zone: hostedZone,
  recordName: 'next',
  target: route53.RecordTarget.fromAlias(new route53targets.CloudFrontTarget(nextDctechDistribution)),
});

new route53.AaaaRecord(this, 'NextDcTechAaaaRecord', {
  zone: hostedZone,
  recordName: 'next',
  target: route53.RecordTarget.fromAlias(new route53targets.CloudFrontTarget(nextDctechDistribution)),
});
```

**Update Cognito Callback URLs:**

```typescript
callbackUrls: [
  'https://organize.dctech.events/callback',
  'https://next.dctech.events/callback',  // ADD next.dctech.events
  'http://localhost:3000/callback'
],
logoutUrls: [
  'https://organize.dctech.events',
  'https://next.dctech.events',  // ADD next.dctech.events
  'http://localhost:3000'
],
```

**Add Lambda Layer for Handlebars templates:**

```typescript
const templatesLayer = new lambda.LayerVersion(this, 'TemplatesLayer', {
  code: lambda.Code.fromAsset('infrastructure/lambda/layers/templates'),
  compatibleRuntimes: [lambda.Runtime.NODEJS_20_X],
  description: 'Handlebars templates for both organize and dctech.events',
});

apiFunction.addLayers(templatesLayer);

// Grant API Lambda read access to templates in S3 (during build)
websiteBucket.grantRead(apiFunction, 'templates/*');
```

**Update API Lambda environment variables:**

```typescript
const lambdaEnv = {
  // ... existing vars ...
  NEXT_DCTECH_DOMAIN: 'next.dctech.events',
  ORGANIZE_DOMAIN: 'organize.dctech.events',
  WEBSITE_BUCKET: websiteBucket.bucketName,
  GITHUB_REPO: 'rosskarchner/dctech.events',  // For syncing groups/events
  GITHUB_TOKEN_SECRET: 'dctech-events/github-token',  // Stored in Secrets Manager
};
```

**Update Cognito domain callback (already exists, just verify):**

Add dctech.events to CORS allowed origins in Cognito domain settings.

### 1.2 Files to Modify

- `infrastructure/lib/infrastructure-stack.ts` - Add distributions, certificates, DNS records, Lambda layer, environment variables

### 1.3 Testing

- Deploy CDK stack changes
- Verify dctech.events certificate created and DNS validated
- Verify CloudFront distribution created and operational
- Verify API Gateway routes dctech.events requests to Lambda

---

## Phase 2: Lambda API Handler Updates (Week 2-3)

### 2.1 Handlebars Template Setup

**Create template infrastructure:**

```
infrastructure/lambda/layers/templates/
├── homepage.hbs
├── week_page.hbs
├── location_page.hbs
├── locations_index.hbs
├── groups_list.hbs
├── submit_event.hbs
├── submit_group.hbs
├── newsletter.hbs
├── partials/
│   ├── events_by_day.hbs
│   ├── event_card.hbs
│   ├── header.hbs
│   ├── footer.hbs
│   └── nav.hbs
└── layouts/
    └── base.hbs
```

**Add Handlebars to package.json:**

```json
{
  "dependencies": {
    "@aws-sdk/client-dynamodb": "^3.400.0",
    "@aws-sdk/lib-dynamodb": "^3.400.0",
    "aws-jwt-verify": "^4.0.0",
    "uuid": "^9.0.0",
    "handlebars": "^4.7.7"  // ADD
  }
}
```

### 2.2 Update Lambda Handler (`infrastructure/lambda/api/index.js`)

**Add site detection:**

```javascript
// Add at top of handler
const determineSite = (event) => {
  const headers = event.headers || {};
  const host = headers.host || headers.Host || '';
  const customHeader = headers['x-site'] || '';

  if (customHeader === 'next' || host.includes('next.dctech.events')) {
    return 'next';
  }
  return 'organize';
};

exports.handler = async (event) => {
  const site = determineSite(event);
  const { path, method, userId, isHtmx } = await parseEvent(event);

  // Route to appropriate handler
  if (site === 'next') {
    return await handleNextRequest(path, method, userId, isHtmx, event);
  } else {
    return await handleOrganizeRequest(path, method, userId, isHtmx, event);
  }
};
```

**Add Handlebars initialization:**

```javascript
const Handlebars = require('handlebars');
const fs = require('fs');
const path = require('path');

// Load templates from Lambda layer
const TEMPLATES_PATH = '/opt/nodejs/templates';

const loadTemplate = (name) => {
  const templatePath = path.join(TEMPLATES_PATH, `${name}.hbs`);
  const templateString = fs.readFileSync(templatePath, 'utf8');
  return Handlebars.compile(templateString);
};

// Register partials
const registerPartials = () => {
  const partialsPath = path.join(TEMPLATES_PATH, 'partials');
  const partialFiles = fs.readdirSync(partialsPath);
  partialFiles.forEach(file => {
    const name = file.replace('.hbs', '');
    const partial = fs.readFileSync(path.join(partialsPath, file), 'utf8');
    Handlebars.registerPartial(name, partial);
  });
};

registerPartials();

// Template rendering helper
const renderTemplate = (name, data) => {
  const template = loadTemplate(name);
  return template(data);
};
```

### 2.3 New Routes for next.dctech.events

Add these route handlers to Lambda:

```javascript
const handleNextRequest = async (path, method, userId, isHtmx, event) => {
  // PUBLIC ROUTES

  // GET / - Homepage with upcoming events
  if (path === '/' && method === 'GET') {
    const events = await getUpcomingEvents();
    const eventsByDay = prepareEventsByDay(events);
    const stats = generateStats(events);

    const html = renderTemplate('homepage', {
      eventsByDay,
      stats,
      isAuthenticated: !!userId,
      isHtmx,
    });

    return ok(html, 'text/html');
  }

  // GET /week/:weekId - Week view
  if (path.match(/^\/week\/(\d{4})-W\d{2}\/$/)) {
    const weekId = path.match(/\/week\/(\d{4}-W\d{2})/)[1];
    const events = await getEventsByWeek(weekId);
    const eventsByDay = prepareEventsByDay(events);

    const html = renderTemplate('week_page', {
      weekId,
      eventsByDay,
      isAuthenticated: !!userId,
      currentWeek: getCurrentWeekId(),
    });

    return ok(html, 'text/html');
  }

  // GET /locations - Location index
  if (path === '/locations/' && method === 'GET') {
    const locations = await getLocationsWithEventCounts();

    const html = renderTemplate('locations_index', {
      locations,
      isAuthenticated: !!userId,
    });

    return ok(html, 'text/html');
  }

  // GET /locations/:state - State-filtered events
  if (path.match(/^\/locations\/[A-Z]{2}\/?$/)) {
    const state = path.match(/\/locations\/([A-Z]{2})/)[1];
    const events = await getEventsByState(state);
    const eventsByDay = prepareEventsByDay(events);
    const cities = [...new Set(events.map(e => e.city))];

    const html = renderTemplate('location_page', {
      state,
      eventsByDay,
      cities,
      isAuthenticated: !!userId,
    });

    return ok(html, 'text/html');
  }

  // GET /locations/:state/:city - City-filtered events
  if (path.match(/^\/locations\/[A-Z]{2}\/[\w-]+\/?$/)) {
    const [, state, city] = path.match(/\/locations\/([A-Z]{2})\/([^/]+)/);
    const events = await getEventsByCity(state, city);
    const eventsByDay = prepareEventsByDay(events);

    const html = renderTemplate('location_page', {
      state,
      city,
      eventsByDay,
      isAuthenticated: !!userId,
    });

    return ok(html, 'text/html');
  }

  // GET /groups - Groups list
  if (path === '/groups/' && method === 'GET') {
    const groups = await getActiveGroups();
    const sortedGroups = groups.sort((a, b) => a.name.localeCompare(b.name));

    const html = renderTemplate('groups_list', {
      groups: sortedGroups,
      isAuthenticated: !!userId,
    });

    return ok(html, 'text/html');
  }

  // GET /newsletter.html - HTML newsletter
  if (path === '/newsletter.html' && method === 'GET') {
    const events = await getUpcomingEvents(14); // Next 2 weeks
    const eventsByDay = prepareEventsByDay(events);

    const html = renderTemplate('newsletter', {
      format: 'html',
      eventsByDay,
    });

    return ok(html, 'text/html');
  }

  // GET /newsletter.txt - Text newsletter
  if (path === '/newsletter.txt' && method === 'GET') {
    const events = await getUpcomingEvents(14);
    const text = renderTextNewsletter(events);

    return ok(text, 'text/plain');
  }

  // GET /sitemap.xml - XML sitemap
  if (path === '/sitemap.xml' && method === 'GET') {
    const sitemap = generateSitemap();
    return ok(sitemap, 'application/xml');
  }

  // PROTECTED ROUTES (require authentication)

  // GET /submit - Event submission form
  if (path === '/submit/' && method === 'GET') {
    if (!userId) {
      return redirect(cognitoLoginUrl(`dctech.events/submit/`));
    }

    const html = renderTemplate('submit_event', {
      user: await getUser(userId),
    });

    return ok(html, 'text/html');
  }

  // POST /submit - Create event
  if (path === '/submit/' && method === 'POST') {
    if (!userId) {
      return forbidden('Authentication required');
    }

    const body = JSON.parse(event.body);
    const eventId = await createEvent({
      ...body,
      createdBy: userId,
      site: 'dctech',
    });

    const html = renderTemplate('event_created_confirmation', {
      eventId,
      title: body.title,
    });

    return ok(html, 'text/html');
  }

  // GET /submit-group - Group submission form
  if (path === '/submit-group/' && method === 'GET') {
    if (!userId) {
      return redirect(cognitoLoginUrl(`dctech.events/submit-group/`));
    }

    const html = renderTemplate('submit_group', {
      user: await getUser(userId),
    });

    return ok(html, 'text/html');
  }

  // POST /submit-group - Create group
  if (path === '/submit-group/' && method === 'POST') {
    if (!userId) {
      return forbidden('Authentication required');
    }

    const body = JSON.parse(event.body);
    const groupId = await createGroup({
      ...body,
      createdBy: userId,
      active: 'false', // Requires admin approval
    });

    const html = renderTemplate('group_created_confirmation', {
      groupId,
      name: body.name,
    });

    return ok(html, 'text/html');
  }

  // Default 404
  return notFound();
};
```

### 2.4 Helper Functions (add to Lambda)

```javascript
// Format events by day (mirrors Flask's prepare_events_by_day)
const prepareEventsByDay = (events) => {
  const eventsByDay = {};

  events.forEach(event => {
    const date = event.eventDate;
    if (!eventsByDay[date]) {
      eventsByDay[date] = {
        date,
        shortDate: formatShortDate(date),
        timeSlots: {},
      };
    }

    const time = event.time || '00:00';
    if (!eventsByDay[date].timeSlots[time]) {
      eventsByDay[date].timeSlots[time] = [];
    }

    eventsByDay[date].timeSlots[time].push({
      ...event,
      formattedTime: formatTime(time),
    });
  });

  // Convert to array and sort
  return Object.values(eventsByDay)
    .sort((a, b) => new Date(a.date) - new Date(b.date))
    .map(day => ({
      ...day,
      timeSlots: Object.entries(day.timeSlots)
        .sort(([timeA], [timeB]) => timeA.localeCompare(timeB))
        .map(([time, events]) => ({ time, events })),
    }));
};

const getUpcomingEvents = async (daysAhead = 90) => {
  const endDate = new Date();
  endDate.setDate(endDate.getDate() + daysAhead);

  // Query DynamoDB organize-events table
  const result = await dynamodb.query({
    TableName: EVENTS_TABLE,
    IndexName: 'dateEventsIndex',
    KeyConditionExpression: 'eventType = :type AND eventDate BETWEEN :start AND :end',
    ExpressionAttributeValues: {
      ':type': 'event',
      ':start': formatDate(new Date()),
      ':end': formatDate(endDate),
    },
  });

  return result.Items;
};

const getEventsByWeek = async (weekId) => {
  // ISO week 2025-W01 → start date to end date
  const [year, week] = weekId.split('-W');
  const start = getDateFromISOWeek(year, week, 1); // Monday
  const end = getDateFromISOWeek(year, week, 7);   // Sunday

  const result = await dynamodb.query({
    TableName: EVENTS_TABLE,
    IndexName: 'dateEventsIndex',
    KeyConditionExpression: 'eventType = :type AND eventDate BETWEEN :start AND :end',
    ExpressionAttributeValues: {
      ':type': 'event',
      ':start': formatDate(start),
      ':end': formatDate(end),
    },
  });

  return result.Items;
};

const getEventsByState = async (state) => {
  // Filter events by state extracted from location field
  const events = await getUpcomingEvents();

  return events.filter(e => {
    const [city, eventState] = extractCityState(e.location);
    return eventState?.toUpperCase() === state.toUpperCase();
  });
};

const getEventsByCity = async (state, city) => {
  const events = await getEventsByState(state);

  return events.filter(e => {
    const [eventCity] = extractCityState(e.location);
    return eventCity?.toLowerCase() === city.toLowerCase();
  });
};

const getActiveGroups = async () => {
  const result = await dynamodb.query({
    TableName: GROUPS_TABLE,
    IndexName: 'activeGroupsIndex',
    KeyConditionExpression: 'active = :active',
    ExpressionAttributeValues: {
      ':active': 'true',
    },
  });

  return result.Items;
};

const generateStats = (events) => {
  const upcomingCount = events.length;
  const locations = [...new Set(events.map(e => e.location))];
  const groups = [...new Set(events.map(e => e.groupId).filter(Boolean))];

  return {
    upcomingCount,
    locationCount: locations.length,
    groupCount: groups.length,
  };
};

const generateSitemap = () => {
  // Generate XML sitemap for SEO
  const baseUrl = 'https://dctech.events';
  const today = formatDate(new Date());

  const urls = [
    { loc: '/', lastmod: today, priority: 1.0 },
    { loc: '/week/LATEST/', lastmod: today, priority: 0.9 },
    { loc: '/locations/', lastmod: today, priority: 0.8 },
    { loc: '/groups/', lastmod: today, priority: 0.8 },
  ];

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map(url => `
  <url>
    <loc>${baseUrl}${url.loc}</loc>
    <lastmod>${url.lastmod}</lastmod>
    <priority>${url.priority}</priority>
  </url>
`).join('')}
</urlset>`;

  return xml;
};
```

### 2.5 Files to Modify/Create

- `infrastructure/lambda/api/index.js` - Add Handlebars setup, dctech routes, helpers
- `infrastructure/lambda/package.json` - Add handlebars dependency
- `infrastructure/lambda/layers/templates/` - Create directory structure with all `.hbs` files

### 2.6 Testing

- Deploy updated Lambda
- Test each dctech.events route in browser
- Verify authentication redirects work
- Verify templates render correctly

---

## Phase 3: Template Migration (Week 2-3, parallel)

### 3.1 Handlebars Templates

Migrate from Jinja2 to Handlebars. Key conversions:

```
Jinja2                          Handlebars
{% extends "base.html" %}       {{> base}}
{% block content %}             {{#*inline "content"}}...{{/inline}}
{% for day in days %}           {{#each days}}
{% endfor %}                    {{/each}}
{% if condition %}              {{#if condition}}
{% endif %}                     {{/if}}
{{ variable }}                  {{variable}}
{{ variable|upper }}            {{upper variable}} (custom helper)
```

### 3.2 Create Templates

Create all templates in `infrastructure/lambda/layers/templates/`:

**base.hbs** - Master layout with header, nav, footer, HTMX script

**homepage.hbs** - Main event listing with:
- Search/filter inputs (using HTMX)
- Events grouped by day
- Submit event CTA (shows "Sign in" if not authenticated)
- Statistics card (N events, M locations)

**week_page.hbs** - ISO week view with:
- Week navigation (previous/next)
- Events for each day of week
- Optional calendar grid view

**location_page.hbs** - Location-filtered view with:
- City/state selector
- Events in that location
- Breadcrumb navigation

**locations_index.hbs** - City/state directory with:
- Links to each location with event counts
- Grouped by state

**groups_list.hbs** - Groups directory with:
- Sorted list of active groups
- Links to group pages (if implemented)
- Event count for each group

**submit_event.hbs** - Event submission form with:
- Fields: title, date, time, location, URL, description
- HTMX form submission (POST /submit/)
- Cognito user info pre-populated

**submit_group.hbs** - Group submission form with:
- Fields: name, website, iCal URL
- HTMX form submission (POST /submit-group/)
- Note: requires admin approval

**newsletter.hbs** - Email newsletter template with:
- Upcoming events for next 2 weeks
- HTML and text variants

**partials/events_by_day.hbs** - Reusable events list
**partials/event_card.hbs** - Single event display
**partials/header.hbs** - Navigation bar with login button
**partials/footer.hbs** - Footer with links
**partials/nav.hbs** - Navigation menu

### 3.3 HTMX Integration

Add HTMX features to templates:

- **Search/Filter**: `hx-get="/api/events?filter=..."` with debounce
- **Form Submission**: `hx-post="/submit/"` with target for success message
- **Location Filter**: `hx-get="/locations/DC"` replaces content

Example template snippet:
```handlebars
<form hx-post="/submit/"
      hx-target="#result"
      hx-swap="innerHTML">
  <input type="text" name="title" required>
  <input type="date" name="eventDate" required>
  <button type="submit">Submit Event</button>
</form>
<div id="result"></div>
```

### 3.4 Files to Create

- `infrastructure/lambda/layers/templates/base.hbs`
- `infrastructure/lambda/layers/templates/homepage.hbs`
- `infrastructure/lambda/layers/templates/week_page.hbs`
- `infrastructure/lambda/layers/templates/location_page.hbs`
- `infrastructure/lambda/layers/templates/locations_index.hbs`
- `infrastructure/lambda/layers/templates/groups_list.hbs`
- `infrastructure/lambda/layers/templates/submit_event.hbs`
- `infrastructure/lambda/layers/templates/submit_group.hbs`
- `infrastructure/lambda/layers/templates/newsletter.hbs`
- `infrastructure/lambda/layers/templates/partials/*.hbs` (6 files)

---

## Phase 4: iCal Aggregation & Data Migration (Week 3-4)

### 4.1 Package Python for Lambda

**Keep existing Python script** (`refresh_calendars.py`) but package as Lambda:

```
infrastructure/lambda/refresh/
├── lambda_function.py     (entry point)
├── refresh_calendars.py   (existing logic)
├── requirements.txt       (dependencies)
└── groups_config.json     (copy of _groups YAML as JSON)
```

**Create wrapper (`lambda_function.py`):**

```python
import json
import os
from refresh_calendars import fetch_ical_and_extract_events
from boto3 import resource as boto_resource

dynamodb = boto_resource('dynamodb')
groups_table = dynamodb.Table(os.environ['GROUPS_TABLE'])
events_table = dynamodb.Table(os.environ['EVENTS_TABLE'])

def lambda_handler(event, context):
    """
    EventBridge scheduled rule calls this every 4 hours.
    Fetches iCal feeds for all active groups and updates DynamoDB.
    """

    # Get all active groups from DynamoDB
    response = groups_table.query(
        IndexName='activeGroupsIndex',
        KeyConditionExpression='active = :active',
        ExpressionAttributeValues={':active': 'true'}
    )

    groups = response['Items']

    for group in groups:
        if not group.get('ical'):
            continue

        try:
            # Fetch iCal feed (reuse existing logic)
            events = fetch_ical_and_extract_events(
                url=group['ical'],
                group_id=group['groupId'],
                group=group
            )

            # Store in DynamoDB
            for event in events:
                event['groupId'] = group['groupId']
                event['eventType'] = 'event'  # Required for GSI
                event['createdBy'] = 'system'
                event['createdAt'] = int(time.time())

                events_table.put_item(Item=event)

            print(f"Updated {len(events)} events for {group['name']}")

        except Exception as e:
            print(f"Error fetching {group['name']}: {str(e)}")

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'iCal refresh complete'})
    }
```

**Add EventBridge rule to CDK:**

```typescript
// Add to infrastructure-stack.ts
const refreshSchedule = new eventbridge.Rule(this, 'RefreshCalendarsSchedule', {
  schedule: eventbridge.Schedule.rate(cdk.Duration.hours(4)),
  description: 'Refresh iCal feeds from 110+ groups',
});

const refreshFunction = new lambda.Function(this, 'RefreshFunction', {
  runtime: lambda.Runtime.PYTHON_3_11,
  handler: 'lambda_function.lambda_handler',
  code: lambda.Code.fromAsset('infrastructure/lambda/refresh'),
  environment: {
    GROUPS_TABLE: groupsTable.tableName,
    EVENTS_TABLE: eventsTable.tableName,
  },
  timeout: cdk.Duration.minutes(5),
  memorySize: 1024,
  description: 'Fetches iCal feeds and updates events in DynamoDB',
});

// Grant permissions
groupsTable.grantReadData(refreshFunction);
eventsTable.grantWriteData(refreshFunction);

// Add target
refreshSchedule.addTarget(new targets.LambdaFunction(refreshFunction));
```

### 4.2 Continuous Syncing from GitHub Repo

**Extend refresh Lambda to sync groups and events from GitHub** (keeps sites in sync during indefinite migration):

The refresh Lambda should do **three things** on every run (every 4 hours):

1. **Sync groups from `_groups/*.yaml`**:
   - Fetch all files from GitHub `/rosskarchner/dctech.events/_groups/` directory
   - Parse YAML content
   - Create/update DynamoDB records in `organize-groups` table
   - Preserve groupId consistency (use filename slug as groupId)

2. **Sync single events from `_single_events/*.yaml`**:
   - Fetch files from GitHub `/rosskarchner/dctech.events/_single_events/` directory
   - Parse YAML content
   - Create/update DynamoDB records in `organize-events` table with `eventType: 'manual'`
   - Use filename date as eventDate

3. **Fetch iCal feeds for all active groups**:
   - Existing logic (already implemented above)
   - Events from iCal have `eventType: 'ical'`

**Updated wrapper (`lambda_function.py`):**

```python
import json
import yaml
import os
import time
from github import Github
from refresh_calendars import fetch_ical_and_extract_events
from boto3 import resource as boto_resource

dynamodb = boto_resource('dynamodb')
groups_table = dynamodb.Table(os.environ['GROUPS_TABLE'])
events_table = dynamodb.Table(os.environ['EVENTS_TABLE'])

# GitHub API (token from Secrets Manager)
github = Github(os.environ['GITHUB_TOKEN'])
repo = github.get_repo(os.environ['GITHUB_REPO'])  # rosskarchner/dctech.events

def sync_groups_from_repo():
    """Sync group definitions from _groups/ directory in repo"""
    groups_synced = 0

    try:
        # Fetch all files in _groups/ directory
        contents = repo.get_contents('_groups')

        for item in contents:
            if not item.name.endswith('.yaml'):
                continue

            try:
                # Parse YAML content
                yaml_content = item.decoded_content.decode('utf-8')
                group_data = yaml.safe_load(yaml_content)

                # Use filename (without .yaml) as groupId for consistency
                group_id = item.name.replace('.yaml', '')

                # Create group record
                group = {
                    'groupId': group_id,
                    'name': group_data.get('name'),
                    'website': group_data.get('website'),
                    'ical': group_data.get('ical'),
                    'active': 'true' if group_data.get('active', True) else 'false',
                    'description': group_data.get('description', ''),
                    'fallback_url': group_data.get('fallback_url'),
                    'createdAt': int(time.time()),
                    'createdBy': 'repo_sync',
                    'sourceFile': item.name,
                    'lastSyncedAt': int(time.time()),
                }

                groups_table.put_item(Item=group)
                groups_synced += 1

            except Exception as e:
                print(f"Error syncing group {item.name}: {str(e)}")

    except Exception as e:
        print(f"Error fetching groups from repo: {str(e)}")

    return groups_synced

def sync_single_events_from_repo():
    """Sync manually submitted events from _single_events/ directory"""
    events_synced = 0

    try:
        contents = repo.get_contents('_single_events')

        for item in contents:
            if not item.name.endswith('.yaml'):
                continue

            try:
                # Parse YAML content
                yaml_content = item.decoded_content.decode('utf-8')
                event_data = yaml.safe_load(yaml_content)

                # Use filename as eventId for consistency
                event_id = item.name.replace('.yaml', '')

                # Create event record
                event = {
                    'eventId': event_id,
                    'title': event_data.get('title'),
                    'description': event_data.get('description', ''),
                    'location': event_data.get('location'),
                    'eventDate': event_data.get('date'),  # YYYY-MM-DD
                    'time': event_data.get('time', '00:00'),  # HH:MM
                    'url': event_data.get('url'),
                    'eventType': 'manual',  # Distinguish from iCal events
                    'createdAt': int(time.time()),
                    'createdBy': 'repo_sync',
                    'sourceFile': item.name,
                    'lastSyncedAt': int(time.time()),
                }

                # Add optional fields
                if event_data.get('end_date'):
                    event['endDate'] = event_data.get('end_date')
                if event_data.get('end_time'):
                    event['endTime'] = event_data.get('end_time')
                if event_data.get('cost'):
                    event['cost'] = event_data.get('cost')

                events_table.put_item(Item=event)
                events_synced += 1

            except Exception as e:
                print(f"Error syncing event {item.name}: {str(e)}")

    except Exception as e:
        print(f"Error fetching events from repo: {str(e)}")

    return events_synced

def lambda_handler(event, context):
    """
    EventBridge scheduled rule calls this every 4 hours.
    Syncs:
    1. Groups from _groups/ YAML files in GitHub repo
    2. Single events from _single_events/ YAML files in GitHub repo
    3. iCal feeds for all active groups

    This keeps next.dctech.events and dctech.events in sync during migration.
    """

    print("Starting sync from GitHub repo and iCal feeds...")

    # Sync groups from repo
    groups_synced = sync_groups_from_repo()
    print(f"Synced {groups_synced} groups from repo")

    # Sync single events from repo
    events_synced = sync_single_events_from_repo()
    print(f"Synced {events_synced} single events from repo")

    # Fetch iCal feeds for active groups
    response = groups_table.query(
        IndexName='activeGroupsIndex',
        KeyConditionExpression='active = :active',
        ExpressionAttributeValues={':active': 'true'}
    )

    groups = response['Items']
    ical_events_synced = 0

    for group in groups:
        if not group.get('ical'):
            continue

        try:
            # Fetch iCal feed
            events = fetch_ical_and_extract_events(
                url=group['ical'],
                group_id=group['groupId'],
                group=group
            )

            # Store in DynamoDB
            for event in events:
                event['groupId'] = group['groupId']
                event['eventType'] = 'ical'  # Mark as iCal source
                event['createdBy'] = 'system'
                event['lastSyncedAt'] = int(time.time())

                events_table.put_item(Item=event)

            ical_events_synced += len(events)
            print(f"Synced {len(events)} iCal events for {group['name']}")

        except Exception as e:
            print(f"Error syncing iCal for {group.get('name')}: {str(e)}")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'groups_synced': groups_synced,
            'single_events_synced': events_synced,
            'ical_events_synced': ical_events_synced,
        })
    }
```

**GitHub Token Setup**:

Store GitHub token in AWS Secrets Manager:

```bash
aws secretsmanager create-secret \
  --name dctech-events/github-token \
  --secret-string "ghp_YOUR_GITHUB_TOKEN"
```

Grant Lambda permission to read the secret in CDK:

```typescript
const githubSecret = secretsmanager.Secret.fromSecretNameV2(
  this, 'GitHubToken',
  'dctech-events/github-token'
);

githubSecret.grantRead(refreshFunction);

refreshFunction.addEnvironment('GITHUB_TOKEN_SECRET_ARN', githubSecret.secretArn);
```

**Benefits of continuous syncing**:
- No separate "migration" event needed
- GitHub remains source of truth during indefinite migration
- Both dctech.events and next.dctech.events always in sync
- New groups/events appear on both sites automatically
- Manual changes to YAML files reflected within 4 hours
- No need for cutover planning - can run both sites indefinitely

### 4.3 Update requirements.txt

Add PyGithub for GitHub API access:

```
PyYAML>=6.0
requests>=2.28.0
icalendar>=5.0.0
boto3>=1.26.0
PyGithub>=2.0.0  # ADD for GitHub repo access
```

### 4.4 Files to Create/Modify

- `infrastructure/lambda/refresh/lambda_function.py` - Update with repo sync + iCal logic
- `infrastructure/lambda/refresh/refresh_calendars.py` - Copy of existing (unchanged)
- `infrastructure/lambda/refresh/requirements.txt` - Add PyGithub dependency
- `infrastructure/lib/infrastructure-stack.ts` - Add EventBridge rule + refresh Lambda + GitHub secret grant

### 4.5 Testing

- Deploy refresh Lambda with GitHub token configured
- Verify Lambda can read from GitHub API (via CloudWatch logs)
- Manually trigger and verify groups appear in DynamoDB
- Manually trigger and verify single events appear in DynamoDB
- Manually trigger and verify iCal events appear in DynamoDB
- Verify all events visible on next.dctech.events

---

## Phase 5: Frontend Assets & Styling (Week 4)

### 5.1 CSS & Static Assets

Copy to S3:
- `infrastructure/frontend/static/css/main.css` → upload to S3 bucket
- `infrastructure/frontend/static/js/htmx-config.js` → upload to S3 bucket
- `infrastructure/frontend/fonts/` → upload to S3 bucket

**Update S3 bucket in CDK:**

```typescript
// Add to stack: sync static assets
const assetSource = core.Source.asset('infrastructure/frontend/static');
// (CDK can do this automatically if needed)
```

### 5.2 Handlebars Custom Helpers

Add to Lambda for formatting:

```javascript
// Register custom Handlebars helpers
Handlebars.registerHelper('upper', (str) => str?.toUpperCase() || '');
Handlebars.registerHelper('formatTime', (time) => {
  // "17:30" → "5:30 pm"
  if (!time) return '';
  const [h, m] = time.split(':');
  const hour = parseInt(h);
  const meridiem = hour >= 12 ? 'pm' : 'am';
  const displayHour = hour > 12 ? hour - 12 : (hour === 0 ? 12 : hour);
  return `${displayHour}:${m} ${meridiem}`;
});

Handlebars.registerHelper('formatDate', (date) => {
  // "2025-12-02" → "Tuesday, December 2"
  return new Date(date).toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric'
  });
});

Handlebars.registerHelper('eq', (a, b) => a === b);
Handlebars.registerHelper('contains', (arr, item) => arr?.includes(item) || false);
```

### 5.3 Files to Create/Modify

- `infrastructure/frontend/static/css/main.css` - Copy or update styling
- `infrastructure/lambda/api/index.js` - Add Handlebars helpers

---

## Phase 6: Testing & Staging Deployment (Week 5)

### 6.1 Local Testing

```bash
# Test Lambda locally
sam local start-api

# Test routes in browser on localhost:3000
curl http://localhost:3000/
curl http://localhost:3000/week/2025-W49/
curl http://localhost:3000/locations/
```

### 6.2 Staging Deployment

1. Deploy to staging environment with different domain (e.g., `beta.dctech.events`)
2. Test all routes
3. Load test with simulated traffic
4. Verify template rendering, HTMX interactions
5. Test authentication flow (Cognito sign-up, login, logout)
6. Verify iCal refresh working

### 6.3 Testing Checklist

- [ ] Homepage loads with events
- [ ] Week view filters to correct week
- [ ] Location filtering works
- [ ] Groups list displays
- [ ] Search/filter HTMX interactions work
- [ ] Unauthenticated users see "Sign in" on submit forms
- [ ] Cognito sign-up works
- [ ] Event submission creates DynamoDB record
- [ ] Group submission creates DynamoDB record
- [ ] Newsletter renders correctly
- [ ] Sitemap generates correct URLs
- [ ] CSS loads and styles correctly
- [ ] No JavaScript errors in console
- [ ] Responsive on mobile

---

## Phase 7: Production Launch to next.dctech.events (Week 5)

### 7.1 Deploy to Production

```bash
# Update CDK stack with production values
cdk deploy

# Verify next.dctech.events certificate created and validated
# Verify CloudFront distribution operational
# Verify Route 53 records configured for next.dctech.events
```

### 7.2 Pre-launch Checklist

- [ ] next.dctech.events certificate validated in Route 53
- [ ] CloudFront distribution operational
- [ ] API Lambda routes working for /next site
- [ ] DynamoDB has all events from initial iCal refresh
- [ ] Staging environment fully tested
- [ ] GitHub token configured in Secrets Manager
- [ ] EventBridge rule created and first refresh completed

### 7.3 Launch next.dctech.events

Site is now live at `https://next.dctech.events/`

- [ ] Homepage loads with events
- [ ] All routes accessible (week, locations, groups, etc.)
- [ ] Events displaying correctly
- [ ] No 5xx errors in Lambda
- [ ] CloudFront working (check cache headers)
- [ ] Cognito authentication working
- [ ] Newsletter generates correctly
- [ ] Sitemap accessible

### 7.4 Monitoring in Production

```typescript
// Already configured in stack, just verify:
// - CloudWatch Alarms for Lambda errors
// - X-Ray tracing enabled
// - CloudFront metrics dashboard
```

---

## Phase 8: Ongoing Operations (Week 6+)

### 8.1 Parallel Operation Strategy

**Both dctech.events and next.dctech.events now run indefinitely in parallel:**

- **dctech.events** (GitHub Pages): Static site continues to work
  - Users can still submit events/groups via GitHub PRs
  - `freeze.py` continues to run on GitHub Actions schedule
  - Serves as fallback if next.dctech.events has issues

- **next.dctech.events** (CDK + Lambda): Dynamic new site
  - Shows same data synced from GitHub repo every 4 hours
  - Users can submit events directly via Cognito auth
  - Always in sync with dctech.events data

### 8.2 Continuous Synchronization

The EventBridge rule runs Lambda every 4 hours to sync:

1. Groups from `_groups/*.yaml` in repo → DynamoDB
2. Single events from `_single_events/*.yaml` in repo → DynamoDB
3. iCal feeds from all active groups → DynamoDB

**Result**: Both sites show identical data without manual intervention.

### 8.3 Monitoring & Maintenance

**CloudWatch Alarms** (already configured):
- Lambda errors > threshold → SNS notification
- DynamoDB throttling → SNS notification

**Manual Checks** (weekly recommended):
- CloudWatch Logs for Lambda refresh function
- DynamoDB table sizes (events/groups counts)
- CloudFront metrics (cache hit ratio, errors)

### 8.4 Future Cutover Planning

When ready to fully migrate to next.dctech.events:
- Update dctech.events DNS to point to CloudFront
- Disable GitHub Pages deployment
- Archive static generation scripts
- Update documentation

**This can be planned and executed separately whenever convenient - no time pressure.**

### 8.5 Optional: User Communication

Consider announcing next.dctech.events to users:
- Beta notice in navigation (if desired)
- "New event submission form now available at next.dctech.events"
- Gradual migration of traffic based on user feedback

### 8.6 DynamoDB Queries for next.dctech.events

The Lambda handler queries for events using:

```python
# Upcoming events (90 days)
response = events_table.query(
    IndexName='dateEventsIndex',
    KeyConditionExpression='eventType = :type AND eventDate BETWEEN :start AND :end',
    ExpressionAttributeValues={
        ':type': 'event',  # Includes both 'ical' and 'manual' events
        ':start': today,
        ':end': plus_90_days,
    },
)

# Active groups
response = groups_table.query(
    IndexName='activeGroupsIndex',
    KeyConditionExpression='active = :active',
    ExpressionAttributeValues={':active': 'true'},
)
```

### 8.7 Optional: Update Export Lambda

The existing Export Lambda (`lambda/export/index.js`) is still useful:
- Continues to export DynamoDB → YAML files
- Useful for backup/archival purposes
- Can be kept indefinitely as a data safeguard

---

## Architecture Summary

```
┌────────────────────────────────────────────────────────────────┐
│    DCTECH.EVENTS (GitHub Pages)  &  NEXT.DCTECH.EVENTS (AWS)   │
│            + ORGANIZE.DCTECH.EVENTS (Existing)                 │
│                    (Unified Infrastructure)                      │
└────────────────────────────────────────────────────────────────┘

                              User Browser
                                   │
                ┌──────────────────┼──────────────────┐
                │                  │                  │
         dctech.events      next.dctech.events  organize.dctech.events
        (GitHub Pages)     (CloudFront+Lambda)   (CloudFront+Lambda)
                    │              │              │
                    └──────────────┼──────────────┘
                                   │
                        CloudFront Distributions
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                 Route 53      API Gateway       S3 Bucket
                    │              │              │
                    │        ┌──────┴──────┐      │
                    │        │             │      │
                    └──────→ Lambda API  ←──────────→ Templates
                             Handler      └─────────  Layer
                             (Node.js)
                                   │
                        ┌──────────┼──────────────┐
                        │          │              │
                    Cognito    DynamoDB      S3 Cache
                  (Auth)     (Events,       (if needed)
                            Groups,
                            Users)
                                   │
                        EventBridge Rule (4h)
                                   │
                    Python Lambda (Refresh + Sync)
                   - Fetches iCal feeds (110+ groups)
                   - Syncs _groups/*.yaml from repo
                   - Syncs _single_events/*.yaml from repo
                                   │
                      ┌────────────┼────────────┐
                      │            │            │
                 GitHub Repo   Meetup.com   Other iCal
                (_groups/)      (feeds)      (feeds)
            (_single_events/)
```

---

## Key Files to Modify/Create

### **Critical (implementation required):**
1. `infrastructure/lib/infrastructure-stack.ts` - Infrastructure changes
2. `infrastructure/lambda/api/index.js` - Lambda handler + routes
3. `infrastructure/lambda/layers/templates/*.hbs` - Handlebars templates
4. `infrastructure/lambda/refresh/lambda_function.py` - iCal refresh wrapper
5. `infrastructure/lambda/package.json` - Add handlebars dependency

### **Important (supporting):**
- `infrastructure/lambda/refresh/requirements.txt` - Python deps
- `infrastructure/frontend/static/css/main.css` - Copy to S3
- `infrastructure/frontend/static/js/htmx-config.js` - Copy to S3

### **Optional (nice to have):**
- CloudWatch Dashboard for monitoring refresh Lambda
- SNS alerts for sync failures
- Documentation on cutover path for future dctech.events → next.dctech.events switch

---

## Rollback Plan

Since next.dctech.events runs in parallel with dctech.events (no cutover), rollback is simple:

1. **During development**: Just delete CloudFront distribution and certificate, keep GitHub Pages running
2. **In production**: Keep both sites running indefinitely
   - If next.dctech.events has issues, users can fall back to dctech.events
   - No DNS cutover needed until/unless you decide to migrate later
   - GitHub Pages serves as permanent fallback

**Zero risk deployment** - dctech.events continues working exactly as before.

---

## Success Criteria

**Core Functionality:**
- ✅ All events visible on next.dctech.events homepage
- ✅ Week/location/group filtering works
- ✅ Groups list displays all active groups
- ✅ Newsletter renders correctly
- ✅ Sitemap generates valid XML

**Data Sync:**
- ✅ Groups from `_groups/*.yaml` appear in DynamoDB within 4 hours
- ✅ Single events from `_single_events/*.yaml` appear in DynamoDB within 4 hours
- ✅ iCal feeds fetch successfully every 4 hours
- ✅ Events from both iCal and repo display on site

**Authentication & Submission:**
- ✅ Cognito sign-up/login works
- ✅ Event submission creates DynamoDB record
- ✅ Group submission creates DynamoDB record
- ✅ Unauthenticated users redirected to login

**Frontend Quality:**
- ✅ Templates render without errors
- ✅ HTMX interactions responsive
- ✅ Mobile responsive
- ✅ CSS loads and styles correctly
- ✅ No JavaScript console errors

**Performance & Reliability:**
- ✅ CloudFront cache working (reasonable hit ratio)
- ✅ No Lambda 5xx errors
- ✅ EventBridge refresh Lambda succeeds every 4 hours
- ✅ <200ms median page load time
- ✅ dctech.events continues working (no impact from new site)
