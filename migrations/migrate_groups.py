#!/usr/bin/env python3
"""
Migrate groups from _groups/*.yaml to DynamoDB config table.

Usage:
    python migrations/migrate_groups.py [--dry-run]
"""

import os
import sys
import glob
import yaml
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import dynamo_data


def load_yaml_groups(groups_dir='_groups'):
    """Load all group YAML files."""
    groups = []
    for file_path in sorted(glob.glob(os.path.join(groups_dir, '*.yaml'))):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                group = yaml.safe_load(f)
                slug = os.path.splitext(os.path.basename(file_path))[0]
                group['id'] = slug
                groups.append((slug, group))
        except Exception as e:
            print(f"  Error loading {file_path}: {e}")
    return groups


def main():
    parser = argparse.ArgumentParser(description='Migrate groups to DynamoDB')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be migrated')
    args = parser.parse_args()

    groups_dir = os.path.join(os.path.dirname(__file__), '..', '_groups')
    print(f"Loading groups from {groups_dir}...")
    groups = load_yaml_groups(groups_dir)
    print(f"Found {len(groups)} groups")

    if args.dry_run:
        print("\n[DRY RUN] Would migrate:")
        for slug, group in groups:
            active = group.get('active', True)
            cats = group.get('categories', [])
            print(f"  GROUP#{slug} - {group.get('name', '?')} (active={active}, categories={cats})")
        return 0

    # Force DynamoDB mode for writing
    dynamo_data._table = None  # Reset cached table

    success = 0
    errors = 0
    for slug, group in groups:
        try:
            dynamo_data.put_group(slug, group)
            print(f"  + GROUP#{slug} ({group.get('name', '?')})")
            success += 1
        except Exception as e:
            print(f"  ! Error migrating {slug}: {e}")
            errors += 1

    print(f"\nMigration complete: {success} succeeded, {errors} failed (of {len(groups)} total)")
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
