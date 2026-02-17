#!/usr/bin/env python3
"""
Migrate event overrides from _event_overrides/*.yaml to DynamoDB config table.

Usage:
    python migrations/migrate_overrides.py [--dry-run]
"""

import os
import sys
import glob
import yaml
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import dynamo_data


def load_yaml_overrides(overrides_dir='_event_overrides'):
    """Load all override YAML files."""
    overrides = []
    for file_path in sorted(glob.glob(os.path.join(overrides_dir, '*.yaml'))):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                override = yaml.safe_load(f)
                guid = os.path.splitext(os.path.basename(file_path))[0]
                if override:
                    overrides.append((guid, override))
        except Exception as e:
            print(f"  Error loading {file_path}: {e}")
    return overrides


def main():
    parser = argparse.ArgumentParser(description='Migrate overrides to DynamoDB')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be migrated')
    args = parser.parse_args()

    overrides_dir = os.path.join(os.path.dirname(__file__), '..', '_event_overrides')
    print(f"Loading overrides from {overrides_dir}...")
    overrides = load_yaml_overrides(overrides_dir)
    print(f"Found {len(overrides)} overrides")

    if args.dry_run:
        print("\n[DRY RUN] Would migrate:")
        for guid, override in overrides:
            print(f"  OVERRIDE#{guid} - fields: {list(override.keys())}")
        return 0

    dynamo_data._table = None

    success = 0
    errors = 0
    for guid, override in overrides:
        try:
            dynamo_data.put_override(guid, override)
            print(f"  + OVERRIDE#{guid} (fields: {list(override.keys())})")
            success += 1
        except Exception as e:
            print(f"  ! Error migrating {guid}: {e}")
            errors += 1

    print(f"\nMigration complete: {success} succeeded, {errors} failed (of {len(overrides)} total)")
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
