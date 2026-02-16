#!/usr/bin/env python3
"""
Migrate single events from _single_events/*.yaml to DynamoDB config table.

Usage:
    python migrations/migrate_single_events.py [--dry-run]
"""

import os
import sys
import glob
import yaml
import hashlib
import argparse
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import dynamo_data


def calculate_event_hash(event_date, event_time, title, url=None):
    """Calculate MD5 hash for event identification (matches generate_month_data.py)."""
    uid_parts = [str(event_date), str(event_time), title]
    if url:
        uid_parts.append(url)
    uid_base = '-'.join(uid_parts)
    return hashlib.md5(uid_base.encode('utf-8')).hexdigest()


def load_yaml_single_events(events_dir='_single_events'):
    """Load all single event YAML files."""
    events = []
    for file_path in sorted(glob.glob(os.path.join(events_dir, '*.yaml'))):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                event = yaml.safe_load(f)
                event_id = os.path.splitext(os.path.basename(file_path))[0]
                event['id'] = event_id

                # Normalize date to string
                if isinstance(event.get('date'), date):
                    event['date'] = event['date'].strftime('%Y-%m-%d')
                if isinstance(event.get('end_date'), date):
                    event['end_date'] = event['end_date'].strftime('%Y-%m-%d')

                # Calculate GUID
                guid = calculate_event_hash(
                    event.get('date', ''),
                    event.get('time', ''),
                    event.get('title', ''),
                    event.get('url'),
                )
                events.append((guid, event))
        except Exception as e:
            print(f"  Error loading {file_path}: {e}")
    return events


def main():
    parser = argparse.ArgumentParser(description='Migrate single events to DynamoDB')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be migrated')
    args = parser.parse_args()

    events_dir = os.path.join(os.path.dirname(__file__), '..', '_single_events')
    print(f"Loading single events from {events_dir}...")
    events = load_yaml_single_events(events_dir)
    print(f"Found {len(events)} single events")

    if args.dry_run:
        print("\n[DRY RUN] Would migrate:")
        for guid, event in events:
            print(f"  EVENT#{guid} - {event.get('title', '?')} ({event.get('date', '?')})")
        return 0

    os.environ['USE_DYNAMO_DATA'] = '1'
    dynamo_data._table = None

    success = 0
    errors = 0
    for guid, event in events:
        try:
            dynamo_data.put_single_event(guid, event)
            print(f"  + EVENT#{guid} ({event.get('title', '?')} - {event.get('date', '?')})")
            success += 1
        except Exception as e:
            print(f"  ! Error migrating {guid}: {e}")
            errors += 1

    print(f"\nMigration complete: {success} succeeded, {errors} failed (of {len(events)} total)")
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
