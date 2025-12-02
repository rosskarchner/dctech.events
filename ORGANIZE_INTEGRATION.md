# Organize DC Tech Events Integration

This document describes how to enable the integrate organize.dctech.events with the main dctech.events site.

## Feature Flags

The integration is controlled by feature flags in `config.yaml`:

```yaml
# Organize DC Tech Events Integration
# Feature flags to control when organize.dctech.events data appears on the main site
organize_integration_enabled: false  # Master switch - must be true for any integration
organize_groups_enabled: false       # Set to true to include groups from organize.dctech.events
organize_events_enabled: false       # Set to true to include events from organize.dctech.events

# URLs for fetching groups and events from organize.dctech.events
organize_groups_url: "https://organize.dctech.events/groups.yaml"
organize_events_url: "https://organize.dctech.events/events.yaml"
```

## How It Works

1. **Master Switch**: `organize_integration_enabled` must be `true` for any integration to work
2. **Granular Control**: You can enable groups and events independently
3. **URLs**: Can use CloudFront distribution URLs or custom domain URLs

## Enabling the Integration

### Step 1: Deploy organize.dctech.events Infrastructure

First, deploy the organize.dctech.events CDK stack:

```bash
cd infrastructure
npx cdk deploy
```

Save the outputs, especially:
- `GroupsYamlUrl`
- `EventsYamlUrl`

### Step 2: Test the Exports

Verify that the YAML exports are working:

```bash
# Test groups export
curl https://organize.dctech.events/groups.yaml

# Test events export
curl https://organize.dctech.events/events.yaml
```

You should see YAML output with the structure matching `_groups/*.yaml` and `_single_events/*.yaml`.

### Step 3: Update config.yaml (Optional)

If you're using CloudFront URLs instead of a custom domain:

```yaml
organize_groups_url: "https://d1234567890abc.cloudfront.net/groups.yaml"
organize_events_url: "https://d1234567890abc.cloudfront.net/events.yaml"
```

### Step 4: Enable Integration

Enable the integration in stages:

#### Test Mode (Only Groups)
```yaml
organize_integration_enabled: true
organize_groups_enabled: true
organize_events_enabled: false
```

Run the build locally to test:
```bash
python3 generate_month_data.py
```

You should see:
```
Fetching groups from https://organize.dctech.events/groups.yaml...
Added group from organize.dctech.events: Test Group
organize.dctech.events events are disabled (organize_events_enabled=false)
```

#### Full Integration
```yaml
organize_integration_enabled: true
organize_groups_enabled: true
organize_events_enabled: true
```

## Disabling the Integration

To disable the integration (e.g., for troubleshooting):

```yaml
organize_integration_enabled: false
```

This will prevent any data from organize.dctech.events from appearing on the main site.

## Build Output

When integration is **enabled**, you'll see:
```
Fetching groups from https://organize.dctech.events/groups.yaml...
Added group from organize.dctech.events: Example Group
Fetching events from https://organize.dctech.events/events.yaml...
Added event from organize.dctech.events: Example Event
```

When integration is **disabled**, you'll see:
```
organize.dctech.events integration is disabled (organize_integration_enabled=false)
organize.dctech.events integration is disabled (organize_integration_enabled=false)
```

## Deployment Workflow

### Safe Rollout

1. **Week 1**: Deploy infrastructure, keep flags disabled
   - Deploy CDK stack
   - Configure and deploy frontend
   - Test locally with flags enabled
   - Commit with flags disabled

2. **Week 2**: Enable groups only
   - Set `organize_integration_enabled: true`
   - Set `organize_groups_enabled: true`
   - Keep `organize_events_enabled: false`
   - Monitor main site build

3. **Week 3**: Enable full integration
   - Set `organize_events_enabled: true`
   - Monitor for any issues

### Rollback

If issues occur, simply set:
```yaml
organize_integration_enabled: false
```

And redeploy. The main site will stop fetching from organize.dctech.events immediately.

## Troubleshooting

### No Data Appearing

1. Check feature flags are enabled in `config.yaml`
2. Verify URLs are correct (test with `curl`)
3. Check build logs for error messages
4. Verify export Lambda is running (check CloudWatch Logs)

### Build Fails

If the build fails when fetching from organize.dctech.events:

1. The `fetch_organize_yaml()` function will log a warning and continue
2. Build will succeed with only local data
3. Check that the URLs are accessible

### Data Not Updating

The export Lambda runs every 5 minutes. If data isn't updating:

1. Check CloudWatch Logs for the export Lambda
2. Verify DynamoDB tables have data
3. Check S3 bucket for `groups.yaml` and `events.yaml`
4. Try manually invoking the export Lambda

## URLs and Endpoints

### Production URLs
- Groups: `https://organize.dctech.events/groups.yaml`
- Events: `https://organize.dctech.events/events.yaml`

### CloudFront URLs (if no custom domain)
- Groups: `https://DISTRIBUTION_ID.cloudfront.net/groups.yaml`
- Events: `https://DISTRIBUTION_ID.cloudfront.net/events.yaml`

Get your CloudFront distribution ID from CDK outputs:
```bash
aws cloudfront list-distributions --query "DistributionList.Items[?Comment=='organize.dctech.events'].Id" --output text
```

## Data Format

The YAML exports match the existing format exactly:

### Groups (`groups.yaml`)
```yaml
example-group:
  active: true
  name: "Example Tech Group"
  ical: ""
  submitted_by: "user-id-or-anonymous"
  submitter_link: ""
  website: "https://example.com"
```

### Events (`events.yaml`)
```yaml
2025-12-01-example-event:
  date: "2025-12-01"
  location: "123 Main St, Washington, DC"
  submitted_by: "user-id-or-anonymous"
  submitter_link: ""
  time: "19:00"
  title: "Example Tech Meetup"
  url: "https://example.com/event"
```

## Security Considerations

- URLs are fetched over HTTPS
- YAML parsing uses `yaml.safe_load()` (safe from code injection)
- Network timeouts prevent build delays (10 seconds max)
- Failed fetches don't break the build
- Data is cached in S3 with 5-minute max-age

## Monitoring

Monitor the integration health:

1. **Build Logs**: Check for "Added X from organize.dctech.events"
2. **CloudWatch**: Monitor export Lambda execution
3. **S3**: Check last-modified times on `groups.yaml` and `events.yaml`
4. **Site**: Verify organize.dctech.events data appears on main calendar

## Questions?

See the main README.md or infrastructure/README.md for more details.
