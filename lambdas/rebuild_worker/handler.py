"""
Rebuild Worker Lambda

Docker Lambda that runs the full site rebuild pipeline:
1. Sync iCal cache from S3
2. Run refresh_calendars.py
3. Run generate_month_data.py
4. Run npm run build (esbuild JS)
5. Run freeze.py (Frozen-Flask static site generation)
6. Sync build/ to S3
7. CloudFront invalidation
8. Sync cache back to S3
"""

import json
import os
import subprocess
import sys
import time
import boto3

s3 = boto3.client('s3')
cloudfront = boto3.client('cloudfront')

SITE_BUCKET = os.environ['SITE_BUCKET']
DATA_CACHE_BUCKET = os.environ['DATA_CACHE_BUCKET']
CLOUDFRONT_DISTRIBUTION_ID = os.environ.get('CLOUDFRONT_DISTRIBUTION_ID', '')
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
    """Main handler - triggered by SQS rebuild queue."""
    start_time = time.time()

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
        # 1. Sync iCal cache from S3
        print("Step 1: Syncing cache from S3...")
        sync_from_s3(DATA_CACHE_BUCKET, 'ical-cache/', os.path.join(WORK_DIR, '_cache', 'ical'))

        # 2. Refresh calendars
        print("Step 2: Refreshing calendars...")
        run_command(['python', 'refresh_calendars.py'])

        # 3. Generate month data
        print("Step 3: Generating month data...")
        run_command(['python', 'generate_month_data.py'])

        # 4. Build JS assets
        print("Step 4: Building JS assets...")
        run_command(['npm', 'run', 'build'])

        # 5. Freeze static site
        print("Step 5: Freezing static site...")
        run_command(['python', 'freeze.py'])

        # 6. Sync build to S3
        print("Step 6: Syncing build to S3...")
        sync_to_s3(os.path.join(WORK_DIR, 'build'), SITE_BUCKET)

        # 7. CloudFront invalidation
        print("Step 7: Invalidating CloudFront...")
        invalidate_cloudfront()

        # 8. Sync cache back to S3
        print("Step 8: Syncing cache back to S3...")
        sync_to_s3(os.path.join(WORK_DIR, '_cache', 'ical'), DATA_CACHE_BUCKET, 'ical-cache')

        elapsed = time.time() - start_time
        print(f"Rebuild completed successfully in {elapsed:.1f}s")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Rebuild completed',
                'elapsed_seconds': round(elapsed, 1),
            }),
        }

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"Rebuild failed after {elapsed:.1f}s: {e}")
        raise
