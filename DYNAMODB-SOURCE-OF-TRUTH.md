# DynamoDB as Source of Truth - Architecture Changes

## Overview

Redesigning DC Tech Events so **DynamoDB is the source of truth** for both events and groups, not the git repository. The repository contains only code, not data.

## Current State (Before Changes)

```
Git Repository
├── Code (Python, templates, etc.) ✓
├── _groups/*.yaml → S3 → Lambda reads → DynamoDB
└── _single_events/*.yaml → S3 → Lambda reads → DynamoDB
```

**Problems:**
- Need to redeploy CDK every time a group/event is added
- Git repo is data store, not just code
- No user submission workflow

## New Architecture (After Changes)

```
Git Repository
└── Code only (Python, infrastructure, etc.)

DynamoDB (Source of Truth)
├── Events Table
│   ├── Auto-collected from iCal feeds (status=approved)
│   └── User-submitted events (status=pending → admin approves → status=approved)
└── Groups Table
    ├── Migrated from _groups/*.yaml (status=approved)
    └── User-submitted groups (status=pending → admin approves → status=approved)
```

## Database Schema Changes

### Events Table (Enhanced)

**New Fields:**
- `status`: "pending" | "approved" | "rejected"
- `submitted_at`: ISO timestamp
- `approval_metadata`: {approved_by, approved_at, rejection_reason}

**New GSI:**
- `StatusIndex` (PK: status, SK: submitted_at) - for admin queries

**Event Sources:**
1. **iCal feeds** - Auto-approved (status="approved")
2. **User submissions** - Start as pending (status="pending")

### Groups Table (New)

**Schema:**
```json
{
  "group_id": "refresh-dc",           // PK
  "name": "Refresh DC",
  "website": "https://refreshdc.org",
  "ical": "https://refreshdc.org/events.ics",
  "fallback_url": "https://refreshdc.org",
  "active": true,
  "scan_for_metadata": true,
  "status": "approved",               // New: pending | approved | rejected
  "submitted_at": "2026-01-11T...",  // New
  "submitted_by": "user@example.com", // New
  "approval_metadata": {...}          // New
}
```

**GSIs:**
1. `StatusIndex` (PK: status, SK: submitted_at) - for admin approval queue
2. `ActiveApprovedIndex` (PK: active_approved, SK: name) - for event collection
   - Composite field: active_approved = `true_approved` (only active+approved groups)

## API Changes

### Public Endpoints (No Auth Required)

**Events:**
- `GET /api/events` - Only shows approved events
- `GET /api/events/upcoming` - Only approved, in-person events
- `GET /api/events/virtual` - Only approved, virtual events
- `GET /api/groups` - Only approved groups

**Submissions:**
- `POST /api/events/submit` - Submit event for approval
  ```json
  {
    "title": "Tech Meetup",
    "date": "2026-02-15",
    "time": "19:00",
    "location": "Washington, DC",
    "url": "https://example.com",
    "submitter_email": "user@example.com"
  }
  ```
  Response: `{"status": "pending", "message": "Event submitted for approval"}`

- `POST /api/groups/submit` - Submit group for approval
  ```json
  {
    "name": "New Tech Group",
    "website": "https://newtechgroup.org",
    "ical": "https://newtechgroup.org/events.ics",
    "submitter_email": "user@example.com"
  }
  ```
  Response: `{"status": "pending", "message": "Group submitted for approval"}`

### Admin Endpoints (Auth Required)

**Events Admin:**
- `GET /api/admin/events/pending` - List pending events
- `GET /api/admin/events/approved` - List approved events
- `GET /api/admin/events/rejected` - List rejected events
- `PUT /api/admin/events/{event_id}/approve` - Approve event
- `PUT /api/admin/events/{event_id}/reject` - Reject event
  ```json
  {"reason": "Does not meet community guidelines"}
  ```
- `DELETE /api/admin/events/{event_id}` - Delete event

**Groups Admin:**
- `GET /api/admin/groups/pending` - List pending groups
- `GET /api/admin/groups/approved` - List approved groups
- `GET /api/admin/groups/rejected` - List rejected groups
- `PUT /api/admin/groups/{group_id}/approve` - Approve group
- `PUT /api/admin/groups/{group_id}/reject` - Reject group
- `PUT /api/admin/groups/{group_id}` - Update group details
- `DELETE /api/admin/groups/{group_id}` - Delete group

**Authentication:**
- Option 1: AWS Cognito User Pool
- Option 2: Simple API key (for initial MVP)
- Option 3: GitHub OAuth (matches existing pattern)

## Event Collection Changes

### Before
```python
# Load groups from S3
groups = load_groups_from_s3()

# Process each group
for group in groups if group.active and group.ical:
    fetch_and_process(group)
```

### After
```python
# Load ONLY approved + active groups from DynamoDB
groups = dynamodb.query(
    IndexName='ActiveApprovedIndex',
    KeyConditionExpression='active_approved = :val',
    ExpressionAttributeValues={':val': 'true_approved'}
)

# Process each group
for group in groups:
    events = fetch_and_process(group)
    # Mark events as approved since they come from approved groups
    for event in events:
        event['status'] = 'approved'
        event['submitted_at'] = now()
```

## Migration Steps

### Step 1: Update Infrastructure ✅ DONE

- [x] Add Groups table to database_stack.py
- [x] Add StatusIndex GSI to Events table
- [x] Update app.py to pass groups_table
- [x] Update application_stack.py to remove S3 deployments
- [x] Update application_stack.py IAM roles

### Step 2: Create Migration Script

Create `scripts/migrate_groups_to_dynamodb.py`:
```python
# Read all _groups/*.yaml files
# For each group:
#   - Create item in Groups table
#   - Set status='approved'
#   - Set submitted_at=now()
#   - Set active=true (from YAML)
```

### Step 3: Update Event Collection Lambda

Modify `lambda/event-collection/refresh_calendars.py`:
- Remove `load_groups_from_s3()`
- Add `load_groups_from_dynamodb()`
- Query `ActiveApprovedIndex`
- Remove `process_single_events()` (no longer needed)

### Step 4: Update Chalice App

Add to `chalice-app/`:
- `chalicelib/groups_db.py` - Groups table operations
- `chalicelib/admin.py` - Admin operations
- `chalicelib/auth.py` - Authentication (initially API key)

Update `app.py`:
- Add submission endpoints (`POST /api/events/submit`, `POST /api/groups/submit`)
- Add admin endpoints (all `/api/admin/*` routes)
- Filter all public queries by `status='approved'`

### Step 5: Update Documentation

Update all docs to reflect new architecture.

### Step 6: Deploy and Test

```bash
# Deploy infrastructure
cd infrastructure
cdk deploy DCTechEvents-Database-prod  # Creates Groups table

# Run migration
python scripts/migrate_groups_to_dynamodb.py

# Deploy application
cdk deploy DCTechEvents-Application-prod

# Test
curl https://API/api/groups  # Should return all approved groups
curl -X POST https://API/api/events/submit -d '{...}'  # Submit test event
```

## Benefits

### For Users
✅ **Easy submissions** - POST to API, no GitHub PR required
✅ **Faster approval** - Admin can approve via API/UI
✅ **Real-time** - Changes appear immediately after approval

### For Admins
✅ **Approval queue** - All pending submissions in one place
✅ **Audit trail** - Who submitted, when, who approved
✅ **Bulk operations** - Approve/reject multiple items
✅ **No Git conflicts** - No merge conflicts on YAML files

### For Developers
✅ **Clean separation** - Code in git, data in database
✅ **No redeployment** - Adding events/groups doesn't require CDK deploy
✅ **Scalable** - Database handles any volume
✅ **Flexible** - Easy to add new fields/features

## Breaking Changes

### For Existing Deployments

1. **Groups migration required**
   - One-time script to load `_groups/*.yaml` → DynamoDB
   - After migration, `_groups/` directory can be archived

2. **Environment variables changed**
   - Old: `DYNAMODB_TABLE_NAME`
   - New: `EVENTS_TABLE_NAME` + `GROUPS_TABLE_NAME`

3. **iCal event source**
   - Still works, but now reads groups from DynamoDB, not S3

4. **Single events**
   - Old: YAML files in `_single_events/`
   - New: Submit via `POST /api/events/submit`
   - Migration: Convert existing single events to submissions

### For Users

- Can no longer submit via GitHub PR (now use API)
- Need admin approval before events/groups appear

## Rollback Plan

If issues arise:

1. **Keep `_groups/` directory** - Don't delete until confirmed working
2. **Database backup** - CDK enables point-in-time recovery
3. **Dual-source period** - Run both S3 and DynamoDB in parallel
4. **Feature flag** - Environment variable to switch sources

## Timeline

### Phase 1: Foundation (Week 1)
- [x] Database schema updates
- [ ] Migration script
- [ ] Update event collection Lambda

### Phase 2: API (Week 2)
- [ ] Submission endpoints
- [ ] Admin endpoints
- [ ] Basic API key auth

### Phase 3: Testing (Week 3)
- [ ] Run migration on test environment
- [ ] Test submission workflow
- [ ] Test admin approval workflow

### Phase 4: Production (Week 4)
- [ ] Run migration on production
- [ ] Monitor for issues
- [ ] Document new workflows

## Next Steps (Immediate)

1. **Review this design** - Make sure it fits your needs
2. **Decide on auth** - API key vs Cognito vs OAuth
3. **Create migration script** - Load groups from YAML to DynamoDB
4. **Update Lambda code** - Read from DynamoDB instead of S3
5. **Add submission endpoints** - POST /api/events/submit, etc.
6. **Add admin endpoints** - Approval workflow
7. **Test end-to-end** - Submit → Approve → Appear in public API
8. **Update documentation** - New submission process

## Questions to Resolve

1. **Authentication method?**
   - API key (simplest)
   - AWS Cognito (most scalable)
   - GitHub OAuth (existing pattern)

2. **Notification on submission?**
   - Email admin when new submission
   - Slack webhook
   - SNS topic

3. **Auto-approval criteria?**
   - Trust certain submitters
   - Auto-approve if certain fields present
   - Always require manual approval

4. **Submission rate limiting?**
   - Per IP? Per email?
   - WAF rules on API Gateway

5. **Admin UI?**
   - Just API (use curl/Postman)
   - Simple web UI
   - Full React admin dashboard

Let me know your preferences and I'll implement the next phase!
