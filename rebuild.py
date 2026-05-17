#!/usr/bin/env python3
"""
Rebuild script: refresh calendars and generate event data.
"""

import os
import sys
import subprocess

os.chdir('/home/theross/projects/dctech.events')

print("=" * 80)
print("REBUILDING DCTECH.EVENTS")
print("=" * 80)

print("\n[1/2] Refreshing calendars...")
result = subprocess.run(
    [sys.executable, 'refresh_calendars.py'],
    capture_output=False,
    text=True
)
if result.returncode != 0:
    print("ERROR: refresh_calendars failed")
    sys.exit(1)

print("\n[2/2] Generating event data...")
result = subprocess.run(
    [sys.executable, 'generate_month_data.py'],
    capture_output=False,
    text=True
)
if result.returncode != 0:
    print("ERROR: generate_month_data failed")
    sys.exit(1)

print("\n" + "=" * 80)
print("BUILD COMPLETE")
print("=" * 80)
print("\nTo view the site locally:")
print("  python app.py")
print("\nTo freeze the site to static HTML:")
print("  python freeze.py")
