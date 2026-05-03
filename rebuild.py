#!/usr/bin/env python3
"""
Rebuild script for the dctech.events multi-site system.
Runs refresh_calendars and generate_month_data for both sites.
"""

import os
import sys
import subprocess

os.chdir('/home/theross/projects/dctech.events')

print("=" * 80)
print("REBUILDING DCTECH.EVENTS - MULTI-SITE BUILD")
print("=" * 80)

for site in ['dctech', 'dcstem']:
    print(f"\n{'='*80}")
    print(f"Processing {site}...")
    print(f"{'='*80}\n")
    
    # Step 1: Refresh calendars
    print(f"[1/2] Refreshing calendars for {site}...")
    result = subprocess.run(
        [sys.executable, 'refresh_calendars.py', '--site', site],
        capture_output=False,
        text=True
    )
    if result.returncode != 0:
        print(f"ERROR: refresh_calendars failed for {site}")
        sys.exit(1)
    
    # Step 2: Generate month data
    print(f"\n[2/2] Generating month data for {site}...")
    result = subprocess.run(
        [sys.executable, 'generate_month_data.py', '--site', site],
        capture_output=False,
        text=True
    )
    if result.returncode != 0:
        print(f"ERROR: generate_month_data failed for {site}")
        sys.exit(1)
    
    print(f"\n✓ {site} rebuild complete!")

print(f"\n{'='*80}")
print("BUILD COMPLETE")
print(f"{'='*80}")
print("\nTo view the site locally:")
print("  python app.py")
print("\nTo freeze the site to static HTML:")
print("  python freeze.py")
