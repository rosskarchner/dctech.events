#!/usr/bin/env python3
"""
Migrate categories from _categories/*.yaml to DynamoDB config table.

Usage:
    python migrations/migrate_categories.py [--dry-run]
"""

import os
import sys
import glob
import yaml
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import dynamo_data


def load_yaml_categories(categories_dir='_categories'):
    """Load all category YAML files."""
    categories = []
    for file_path in sorted(glob.glob(os.path.join(categories_dir, '*.yaml'))):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                category = yaml.safe_load(f)
                slug = os.path.splitext(os.path.basename(file_path))[0]
                category['slug'] = slug
                categories.append((slug, category))
        except Exception as e:
            print(f"  Error loading {file_path}: {e}")
    return categories


def main():
    parser = argparse.ArgumentParser(description='Migrate categories to DynamoDB')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be migrated')
    args = parser.parse_args()

    categories_dir = os.path.join(os.path.dirname(__file__), '..', '_categories')
    print(f"Loading categories from {categories_dir}...")
    categories = load_yaml_categories(categories_dir)
    print(f"Found {len(categories)} categories")

    if args.dry_run:
        print("\n[DRY RUN] Would migrate:")
        for slug, cat in categories:
            print(f"  CATEGORY#{slug} - {cat.get('name', '?')}")
        return 0

    dynamo_data._table = None

    success = 0
    errors = 0
    for slug, category in categories:
        try:
            dynamo_data.put_category(slug, category)
            print(f"  + CATEGORY#{slug} ({category.get('name', '?')})")
            success += 1
        except Exception as e:
            print(f"  ! Error migrating {slug}: {e}")
            errors += 1

    print(f"\nMigration complete: {success} succeeded, {errors} failed (of {len(categories)} total)")
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
