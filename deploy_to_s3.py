#!/usr/bin/env python3
"""
Deploy the built site to S3 for dcstem.
"""

import subprocess
import sys
import os

os.chdir('/home/theross/projects/dctech.events')

print("Deploying dcstem to S3...")

# Deploy dcstem build to S3
result = subprocess.run(
    ['aws', 's3', 'sync', 'build/dcstem/', 's3://dcstem-events-site/', '--delete'],
    capture_output=True,
    text=True
)

print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

if result.returncode != 0:
    print(f"ERROR: Deployment failed with return code {result.returncode}")
    sys.exit(1)

print("\n✓ Deployment to S3 complete!")

# Invalidate CloudFront
print("\nInvalidating CloudFront cache...")
result = subprocess.run(
    [
        'aws', 'cloudfront', 'list-distributions',
        '--query', "DistributionList.Items[?Aliases.Items && contains(Aliases.Items, 'dc.localstem.events')].Id",
        '--output', 'text'
    ],
    capture_output=True,
    text=True
)

dist_id = result.stdout.strip()
if dist_id and dist_id != 'None':
    print(f"Found CloudFront distribution: {dist_id}")
    result = subprocess.run(
        ['aws', 'cloudfront', 'create-invalidation', '--distribution-id', dist_id, '--paths', '/*'],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    print("✓ CloudFront invalidation complete!")
else:
    print("Warning: Could not find CloudFront distribution for dc.localstem.events")

print("\n✓ Deploy complete!")
