#!/usr/bin/env python3
"""
Track new events by persisting upcoming.yaml to S3 and detecting changes.

This script:
1. Uploads the current upcoming.yaml to S3 with a timestamp
2. Compares with the previous version to identify newly added events
3. Maintains metadata about when each event was first seen

Environment Variables:
- S3_BUCKET: S3 bucket name for storing event history
- AWS_REGION: AWS region (default: us-east-1)

Usage:
    python track_events.py
    python track_events.py --dry-run  # Test without uploading to S3
"""

import os
import sys
import yaml
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

# AWS imports
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    print("Error: boto3 not installed. Run: pip install boto3")
    sys.exit(1)

# Constants
DATA_DIR = '_data'
UPCOMING_FILE = os.path.join(DATA_DIR, 'upcoming.yaml')
HISTORY_PREFIX = 'upcoming-history/'
LATEST_KEY = 'upcoming-history/latest.yaml'
METADATA_KEY = 'upcoming-history/metadata.json'

# Get S3 configuration from environment
S3_BUCKET = os.environ.get('S3_BUCKET', '')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')


def get_s3_client():
    """Get configured S3 client."""
    return boto3.client('s3', region_name=AWS_REGION)


def load_yaml_file(file_path):
    """Load YAML file and return contents."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return None


def download_from_s3(s3_client, bucket, key):
    """Download a file from S3 and return its contents."""
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return response['Body'].read().decode('utf-8')
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            return None
        raise
    except Exception as e:
        print(f"Error downloading from S3: {e}")
        return None


def upload_to_s3(s3_client, bucket, key, content, content_type='text/plain'):
    """Upload content to S3."""
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content,
            ContentType=content_type
        )
        return True
    except Exception as e:
        print(f"Error uploading to S3: {e}")
        return False


def get_event_key(event):
    """
    Generate a unique key for an event.
    
    For iCal events, use the guid field.
    For manual events, use the id field.
    For other events, use a combination of date, time, and title.
    """
    if event.get('guid'):
        return f"guid:{event['guid']}"
    elif event.get('id'):
        return f"id:{event['id']}"
    else:
        # Fallback: use date + time + title
        date = event.get('date', '')
        time = event.get('time', '')
        title = event.get('title', '')
        return f"event:{date}:{time}:{title}"


def compare_events(current_events, previous_events):
    """
    Compare current and previous events to find new ones.
    
    Returns:
        Tuple of (new_events, metadata_updates)
        - new_events: List of events that are new
        - metadata_updates: Dict mapping event keys to first_seen timestamps
    """
    # Build set of previous event keys
    previous_keys = set()
    if previous_events:
        for event in previous_events:
            previous_keys.add(get_event_key(event))
    
    # Find new events
    new_events = []
    current_timestamp = datetime.now(timezone.utc).isoformat()
    
    for event in current_events:
        event_key = get_event_key(event)
        if event_key not in previous_keys:
            new_events.append(event)
    
    return new_events


def load_metadata(s3_client, bucket):
    """Load event metadata from S3."""
    content = download_from_s3(s3_client, bucket, METADATA_KEY)
    if content:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            print("Warning: Could not parse metadata.json, starting fresh")
            return {}
    return {}


def save_metadata(s3_client, bucket, metadata, dry_run=False):
    """Save event metadata to S3."""
    if dry_run:
        print(f"\n[DRY RUN] Would save metadata with {len(metadata)} entries")
        return True
    
    content = json.dumps(metadata, indent=2, ensure_ascii=False)
    return upload_to_s3(s3_client, bucket, METADATA_KEY, content, 'application/json')


def update_metadata(metadata, new_events):
    """
    Update metadata with new events.
    
    Args:
        metadata: Existing metadata dict
        new_events: List of new events to add
        
    Returns:
        Updated metadata dict and count of newly added entries
    """
    current_timestamp = datetime.now(timezone.utc).isoformat()
    newly_added = 0
    
    for event in new_events:
        event_key = get_event_key(event)
        if event_key not in metadata:
            metadata[event_key] = {
                'first_seen': current_timestamp,
                'title': event.get('title', ''),
                'date': event.get('date', ''),
                'url': event.get('url', '')
            }
            newly_added += 1
    
    return metadata, newly_added


def persist_to_s3(dry_run=False):
    """
    Main function to persist upcoming.yaml to S3 and track changes.
    
    Returns:
        Tuple of (success: bool, new_events_count: int, new_events: list)
    """
    if not S3_BUCKET:
        print("Error: S3_BUCKET environment variable not set")
        return False, 0, []
    
    # Check if upcoming.yaml exists
    if not os.path.exists(UPCOMING_FILE):
        print(f"Error: {UPCOMING_FILE} not found")
        return False, 0, []
    
    # Load current events
    current_events = load_yaml_file(UPCOMING_FILE)
    if current_events is None:
        print("Error: Could not load upcoming.yaml")
        return False, 0, []
    
    print(f"Loaded {len(current_events)} events from {UPCOMING_FILE}")
    
    # Get S3 client
    try:
        s3_client = get_s3_client()
    except NoCredentialsError:
        print("Error: AWS credentials not configured")
        return False, 0, []
    
    # Download previous version from S3
    previous_content = download_from_s3(s3_client, S3_BUCKET, LATEST_KEY)
    previous_events = []
    if previous_content:
        try:
            previous_events = yaml.safe_load(previous_content)
            print(f"Loaded {len(previous_events)} events from previous version")
        except yaml.YAMLError as e:
            print(f"Warning: Could not parse previous version: {e}")
    else:
        print("No previous version found in S3 (this is normal for first run)")
    
    # Compare and find new events
    new_events = compare_events(current_events, previous_events)
    print(f"Found {len(new_events)} new events")
    
    # Load and update metadata
    metadata = load_metadata(s3_client, S3_BUCKET)
    metadata, newly_added = update_metadata(metadata, new_events)
    
    if newly_added > 0:
        print(f"Added {newly_added} new entries to metadata")
    
    # Generate timestamp for this version
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d-%H-%M-%S')
    timestamped_key = f"{HISTORY_PREFIX}{timestamp}.yaml"
    
    # Read the upcoming.yaml file content
    with open(UPCOMING_FILE, 'r', encoding='utf-8') as f:
        upcoming_content = f.read()
    
    if dry_run:
        print("\n=== DRY RUN - Would perform these S3 operations ===")
        print(f"Bucket: {S3_BUCKET}")
        print(f"1. Upload to: {timestamped_key}")
        print(f"2. Upload to: {LATEST_KEY}")
        print(f"3. Update metadata with {newly_added} new entries")
        print(f"Total events: {len(current_events)}")
        print(f"New events: {len(new_events)}")
        if new_events:
            print("\nNew events:")
            for event in new_events[:5]:  # Show first 5
                print(f"  - {event.get('title', 'Unknown')} ({event.get('date', 'No date')})")
            if len(new_events) > 5:
                print(f"  ... and {len(new_events) - 5} more")
        print("=== End of dry run ===\n")
        return True, len(new_events), new_events
    
    # Upload to S3 with timestamp
    print(f"Uploading to S3: {timestamped_key}")
    if not upload_to_s3(s3_client, S3_BUCKET, timestamped_key, upcoming_content):
        print("Error: Failed to upload timestamped version")
        return False, 0, []
    
    # Upload as latest version
    print(f"Uploading to S3: {LATEST_KEY}")
    if not upload_to_s3(s3_client, S3_BUCKET, LATEST_KEY, upcoming_content):
        print("Error: Failed to upload latest version")
        return False, 0, []
    
    # Save updated metadata
    if not save_metadata(s3_client, S3_BUCKET, metadata):
        print("Warning: Failed to save metadata")
    
    print(f"✓ Successfully persisted upcoming.yaml to S3")
    print(f"✓ New events detected: {len(new_events)}")
    
    return True, len(new_events), new_events


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Track events by persisting upcoming.yaml to S3'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Test without uploading to S3'
    )
    
    args = parser.parse_args()
    
    success, count, new_events = persist_to_s3(dry_run=args.dry_run)
    
    if success:
        print(f"\nSummary: {count} new events tracked")
        return 0
    else:
        print("\nError: Event tracking failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
