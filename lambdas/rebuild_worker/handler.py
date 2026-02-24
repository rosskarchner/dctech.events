"""
Rebuild Worker Lambda

Supports two modes:
1. **Site rebuild** (default): Build static site from DynamoDB and deploy
   - npm run build → freeze.py → S3 sync → CloudFront invalidation
2. **iCal refresh** (ICAL_REFRESH_MODE=true): Fetch iCal feeds and write to DynamoDB
   - refresh_calendars.py writes events directly to config table
   - Config table changes then trigger site rebuild via DynamoDB Streams
"""

import json
import os
import subprocess
import sys
import time
import boto3

s3 = boto3.client('s3')
cloudfront = boto3.client('cloudfront')

SITE_BUCKET = os.environ.get('SITE_BUCKET', '')
DATA_CACHE_BUCKET = os.environ.get('DATA_CACHE_BUCKET', '')
CLOUDFRONT_DISTRIBUTION_ID = os.environ.get('CLOUDFRONT_DISTRIBUTION_ID', '')
ICAL_REFRESH_MODE = os.environ.get('ICAL_REFRESH_MODE', 'false').lower() == 'true'
WORK_DIR = '/tmp/site'
PROJECT_SOURCE = '/opt/site'  # baked into Docker image at build time


def run_command(cmd_list, cwd=None, env=None):
    """Run a command and return stdout. Raises on failure.
    
    Args:
        cmd_list: List of command arguments (e.g., ['python', 'script.py'])
        cwd: Working directory (defaults to WORK_DIR)
        env: Additional environment variables
    """
    merged_env = {**os.environ, **(env or {})}
    print(f"Running: {' '.join(cmd_list)}")
    result = subprocess.run(
        cmd_list, shell=False, cwd=cwd or WORK_DIR,
        capture_output=True, text=True, env=merged_env,
        timeout=600,
    )
    if result.stdout:
        print(result.stdout[-2000:])  # Truncate long output
    if result.returncode != 0:
        print(f"STDERR: {result.stderr[-2000:]}")
        raise RuntimeError(f"Command failed (exit {result.returncode}): {' '.join(cmd_list)}")
    return result.stdout


def sync_from_s3(bucket, prefix, local_dir):
    """Download files from S3 prefix to local directory."""
    os.makedirs(local_dir, exist_ok=True)
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get('Contents', []):
            key = obj['Key']
            relative = key[len(prefix):].lstrip('/')
            if not relative:
                continue
            local_path = os.path.join(local_dir, relative)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            s3.download_file(bucket, key, local_path)
    print(f"Synced s3://{bucket}/{prefix} -> {local_dir}")


def sync_to_s3(local_dir, bucket, prefix=''):
    """Upload local directory to S3."""
    for root, dirs, files in os.walk(local_dir):
        for fname in files:
            local_path = os.path.join(root, fname)
            relative = os.path.relpath(local_path, local_dir)
            s3_key = f"{prefix}/{relative}" if prefix else relative
            s3_key = s3_key.replace('\\', '/')

            # Set content type based on extension
            content_type = _guess_content_type(fname)
            extra_args = {'ContentType': content_type} if content_type else {}

            s3.upload_file(local_path, bucket, s3_key, ExtraArgs=extra_args)
    print(f"Synced {local_dir} -> s3://{bucket}/{prefix}")


def _guess_content_type(filename):
    """Guess content type from file extension."""
    ext_map = {
        '.html': 'text/html',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.xml': 'application/xml',
        '.ics': 'text/calendar',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.svg': 'image/svg+xml',
        '.ico': 'image/x-icon',
        '.txt': 'text/plain',
        '.woff2': 'font/woff2',
        '.woff': 'font/woff',
    }
    ext = os.path.splitext(filename)[1].lower()
    return ext_map.get(ext)


def invalidate_cloudfront():
    """Create CloudFront invalidation for all paths."""
    if not CLOUDFRONT_DISTRIBUTION_ID:
        print("No CloudFront distribution ID set, skipping invalidation")
        return

    cloudfront.create_invalidation(
        DistributionId=CLOUDFRONT_DISTRIBUTION_ID,
        InvalidationBatch={
            'Paths': {
                'Quantity': 1,
                'Items': ['/*'],
            },
            'CallerReference': str(int(time.time())),
        },
    )
    print(f"CloudFront invalidation created for distribution {CLOUDFRONT_DISTRIBUTION_ID}")


def lambda_handler(event, context):
    """Main handler - supports rebuild (SQS) and iCal refresh (EventBridge) modes."""
    start_time = time.time()

    if not ICAL_REFRESH_MODE:
        for record in event.get('Records', []):
            body = json.loads(record.get('body', '{}'))
            print(f"Rebuild triggered: {json.dumps(body)}")

    # Setup workspace: copy project source from /opt/site to writable /tmp/site
    import shutil
    if os.path.exists(WORK_DIR):
        shutil.rmtree(WORK_DIR)
    shutil.copytree(PROJECT_SOURCE, WORK_DIR, symlinks=False)
    print(f"Copied project source from {PROJECT_SOURCE} to {WORK_DIR}")

    try:
        if ICAL_REFRESH_MODE:
            # iCal refresh mode: fetch feeds and write events to config table
            print("Running in iCal refresh mode...")

            # Sync iCal cache from S3 for ETag/Last-Modified headers
            if DATA_CACHE_BUCKET:
                sync_from_s3(DATA_CACHE_BUCKET, 'ical-cache/', os.path.join(WORK_DIR, '_cache', 'ical'))

            print("Step 1: Refreshing calendars (writing to DynamoDB)...")
            run_command(['python', 'refresh_calendars.py'])

            # Sync cache back to S3 for next run
            if DATA_CACHE_BUCKET:
                sync_to_s3(os.path.join(WORK_DIR, '_cache', 'ical'), DATA_CACHE_BUCKET, 'ical-cache')

        else:
            # Site rebuild mode: build static site from DynamoDB
            print("Running in site rebuild mode...")

            # 1. Build JS assets
            print("Step 1: Building JS assets...")
            run_command(['npm', 'run', 'build'])

            # 2. Freeze static site
            print("Step 2: Freezing static site...")
            run_command(['python', 'freeze.py'])

            # 3. Sync build to S3
            print("Step 3: Syncing build to S3...")
            sync_to_s3(os.path.join(WORK_DIR, 'build'), SITE_BUCKET)

            # 4. CloudFront invalidation
            print("Step 4: Invalidating CloudFront...")
            invalidate_cloudfront()

        mode = 'iCal refresh' if ICAL_REFRESH_MODE else 'Rebuild'
        elapsed = time.time() - start_time
        print(f"{mode} completed successfully in {elapsed:.1f}s")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'{mode} completed',
                'elapsed_seconds': round(elapsed, 1),
            }),
        }

    except Exception as e:
        mode = 'iCal refresh' if ICAL_REFRESH_MODE else 'Rebuild'
        elapsed = time.time() - start_time
        print(f"{mode} failed after {elapsed:.1f}s: {e}")
        raise
