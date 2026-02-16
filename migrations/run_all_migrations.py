#!/usr/bin/env python3
"""
Orchestrator for all YAML -> DynamoDB migration scripts.

Usage:
    python migrations/run_all_migrations.py [--dry-run]
"""

import os
import sys
import subprocess
import argparse


SCRIPTS = [
    ('Categories', 'migrate_categories.py'),
    ('Groups', 'migrate_groups.py'),
    ('Single Events', 'migrate_single_events.py'),
    ('Overrides', 'migrate_overrides.py'),
]


def main():
    parser = argparse.ArgumentParser(description='Run all YAML -> DynamoDB migrations')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be migrated')
    args = parser.parse_args()

    migrations_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(migrations_dir)

    print("=" * 60)
    print("DC Tech Events: YAML -> DynamoDB Migration")
    print("=" * 60)
    if args.dry_run:
        print("[DRY RUN MODE]")
    print()

    results = {}
    overall_success = True

    for name, script in SCRIPTS:
        print(f"\n{'─' * 40}")
        print(f"Running: {name} ({script})")
        print(f"{'─' * 40}")

        cmd = [sys.executable, os.path.join(migrations_dir, script)]
        if args.dry_run:
            cmd.append('--dry-run')

        result = subprocess.run(cmd, cwd=project_root)
        success = result.returncode == 0
        results[name] = success

        if not success:
            overall_success = False
            print(f"\n*** {name} migration FAILED ***")

    # Summary
    print(f"\n{'=' * 60}")
    print("Migration Summary")
    print(f"{'=' * 60}")
    for name, success in results.items():
        status = 'OK' if success else 'FAILED'
        print(f"  {name}: {status}")

    if overall_success:
        print("\nAll migrations completed successfully!")
        if not args.dry_run:
            print("\nNext steps:")
            print("  1. Verify: query DynamoDB table 'dctech-events' and confirm counts")
            print("  2. Test: USE_DYNAMO_DATA=1 python generate_month_data.py")
            print("  3. Compare output against YAML-based run")
    else:
        print("\nSome migrations failed. Check output above for details.")

    return 0 if overall_success else 1


if __name__ == '__main__':
    sys.exit(main())
