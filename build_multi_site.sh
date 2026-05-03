#!/bin/bash
# Multi-site build wrapper
# Builds and deploys both dctech.events and dc.localstem.events

set -e

SITES=("dctech" "dcstem")

echo "=== Multi-Site Build ==="
for site in "${SITES[@]}"; do
    echo ""
    echo "Building site: $site"
    echo "--- Refreshing calendars ---"
    python generate_month_data.py --site "$site"
done

echo ""
echo "--- Freezing sites ---"
python freeze.py

echo ""
echo "=== Build Complete ==="
ls -la build/
