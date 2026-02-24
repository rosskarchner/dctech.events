#!/usr/bin/env python3
"""
Migration: Consolidate DcTechEvents materialized table into dctech-events config table.

Reads all active events from DcTechEvents and creates EVENT#{guid}/META entries
in the config table with source='ical' and all GSI keys populated.
Merges existing OVERRIDE entities into their target EVENTs with an 'overrides' map.

Usage:
    python migrations/consolidate_tables.py --dry-run
    python migrations/consolidate_tables.py
"""

import argparse
import os
import sys
import time

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

# Add parent dir for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CONFIG_TABLE_NAME = os.environ.get('CONFIG_TABLE_NAME', 'dctech-events')
MATERIALIZED_TABLE_NAME = os.environ.get('MATERIALIZED_TABLE_NAME', 'DcTechEvents')


def get_all_materialized_events():
    """Read all events from the DcTechEvents materialized table."""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(MATERIALIZED_TABLE_NAME)

    items = []
    response = table.scan()
    items.extend(response.get('Items', []))
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))

    print(f"Found {len(items)} events in {MATERIALIZED_TABLE_NAME}")
    return items


def get_all_overrides():
    """Read all OVERRIDE entities from the config table."""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(CONFIG_TABLE_NAME)

    items = []
    response = table.scan(
        FilterExpression=Attr('PK').begins_with('OVERRIDE#') & Attr('SK').eq('META'),
    )
    items.extend(response.get('Items', []))
    while 'LastEvaluatedKey' in response:
        response = table.scan(
            FilterExpression=Attr('PK').begins_with('OVERRIDE#') & Attr('SK').eq('META'),
            ExclusiveStartKey=response['LastEvaluatedKey'],
        )
        items.extend(response.get('Items', []))

    overrides = {}
    for item in items:
        guid = item['PK'].split('#', 1)[1]
        overrides[guid] = item
    print(f"Found {len(overrides)} overrides in {CONFIG_TABLE_NAME}")
    return overrides


def get_existing_config_events():
    """Read existing EVENT entities from config table to avoid overwriting."""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(CONFIG_TABLE_NAME)

    items = []
    response = table.scan(
        FilterExpression=Attr('PK').begins_with('EVENT#') & Attr('SK').eq('META'),
    )
    items.extend(response.get('Items', []))
    while 'LastEvaluatedKey' in response:
        response = table.scan(
            FilterExpression=Attr('PK').begins_with('EVENT#') & Attr('SK').eq('META'),
            ExclusiveStartKey=response['LastEvaluatedKey'],
        )
        items.extend(response.get('Items', []))

    existing = {}
    for item in items:
        guid = item['PK'].split('#', 1)[1]
        existing[guid] = item
    print(f"Found {len(existing)} existing EVENT entities in config table")
    return existing


def build_event_item(mat_event, override, existing_config):
    """Build a consolidated EVENT item from materialized event + override."""
    guid = mat_event['eventId']
    date_val = str(mat_event.get('date', ''))
    time_val = str(mat_event.get('time', ''))
    created_at = mat_event.get('createdAt', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))

    # Determine source — if it exists in config table as manual/submitted, keep that
    if existing_config:
        source = existing_config.get('source', 'ical')
    else:
        source = mat_event.get('source', 'ical')

    item = {
        'PK': f'EVENT#{guid}',
        'SK': 'META',
        'source': source,
        'status': 'ACTIVE',
        'createdAt': created_at,
    }

    # Copy event fields
    for field in ['title', 'date', 'time', 'end_date', 'end_time',
                  'location', 'url', 'cost', 'description', 'group',
                  'group_website', 'categories', 'city', 'state',
                  'location_type', 'hidden', 'duplicate_of',
                  'also_published_by']:
        val = mat_event.get(field)
        if val is not None:
            item[field] = val

    # Merge override fields and build overrides map
    overrides_map = {}
    if override:
        override_fields = ['categories', 'title', 'url', 'location', 'time',
                          'hidden', 'duplicate_of']
        for field in override_fields:
            if field in override and field not in ('PK', 'SK'):
                item[field] = override[field]
                overrides_map[field] = True

    if overrides_map:
        item['overrides'] = overrides_map

    # Set GSI keys
    if date_val:
        item['GSI1PK'] = f'DATE#{date_val}'
        item['GSI1SK'] = f'TIME#{time_val}' if time_val else 'TIME#'

    categories = item.get('categories', [])
    if categories and isinstance(categories, list) and len(categories) > 0:
        item['GSI2PK'] = f'CATEGORY#{categories[0]}'
        item['GSI2SK'] = f'DATE#{date_val}'

    if created_at:
        month_key = str(created_at)[:7]
        item['GSI3PK'] = f'CREATED#{month_key}'
        item['GSI3SK'] = str(created_at)

    if date_val:
        item['GSI4PK'] = 'EVT#ACTIVE'
        item['GSI4SK'] = f'{date_val}#{time_val}' if time_val else date_val

    return item


def migrate(dry_run=False):
    """Run the consolidation migration."""
    mat_events = get_all_materialized_events()
    overrides = get_all_overrides()
    existing_config = get_existing_config_events()

    dynamodb = boto3.resource('dynamodb')
    config_table = dynamodb.Table(CONFIG_TABLE_NAME)

    # Track counts
    created = 0
    skipped_manual = 0
    merged_overrides = 0

    for mat_event in mat_events:
        guid = mat_event.get('eventId')
        if not guid:
            continue

        # Skip if this is already a manual/submitted event in config table
        existing = existing_config.get(guid)
        if existing and existing.get('source') in ('manual', 'submitted'):
            skipped_manual += 1
            continue

        override = overrides.get(guid)
        if override:
            merged_overrides += 1

        item = build_event_item(mat_event, override, existing)

        if dry_run:
            if created < 5:
                print(f"  [DRY RUN] Would write: EVENT#{guid} - {item.get('title', '?')}")
        else:
            config_table.put_item(Item=item)

        created += 1

    print(f"\nMigration {'(DRY RUN) ' if dry_run else ''}Summary:")
    print(f"  Events created/updated: {created}")
    print(f"  Skipped (manual/submitted): {skipped_manual}")
    print(f"  Overrides merged: {merged_overrides}")
    print(f"  Total materialized events: {len(mat_events)}")

    if not dry_run:
        print(f"\nMigration complete. {created} events written to {CONFIG_TABLE_NAME}.")
    else:
        print(f"\nDry run complete. No changes made.")


def main():
    parser = argparse.ArgumentParser(description='Consolidate DcTechEvents into config table')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without writing')
    args = parser.parse_args()

    migrate(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
