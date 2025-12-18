#!/usr/bin/env python3
"""
Utility to prune old events from the _single_events directory.
Removes events that occurred more than a week ago.
"""
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
import argparse


SINGLE_EVENTS_DIR = '_single_events'
DAYS_TO_KEEP = 7


def parse_date_from_filename(filename):
    """
    Parse the date from an event filename.
    
    Expected format: YYYY-MM-DD-event-title.yaml
    
    Args:
        filename: The filename to parse
        
    Returns:
        datetime.date object if date is found, None otherwise
    """
    # Match pattern: YYYY-MM-DD at the start of the filename
    match = re.match(r'^(\d{4})-(\d{2})-(\d{2})-', filename)
    if match:
        try:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            return datetime(year, month, day).date()
        except ValueError:
            # Invalid date values
            return None
    return None


def get_old_events(events_dir, cutoff_date):
    """
    Find all event files that are older than the cutoff date.
    
    Args:
        events_dir: Path to the events directory
        cutoff_date: datetime.date object representing the cutoff
        
    Returns:
        List of Path objects for old event files
    """
    old_events = []
    events_path = Path(events_dir)
    
    if not events_path.exists():
        print(f"Warning: Events directory '{events_dir}' does not exist")
        return old_events
    
    for event_file in events_path.glob('*.yaml'):
        event_date = parse_date_from_filename(event_file.name)
        if event_date and event_date < cutoff_date:
            old_events.append(event_file)
    
    return old_events


def prune_events(events_dir=SINGLE_EVENTS_DIR, days_to_keep=DAYS_TO_KEEP, dry_run=False):
    """
    Prune old events from the events directory.
    
    Args:
        events_dir: Path to the events directory
        days_to_keep: Number of days to keep events for
        dry_run: If True, only print what would be deleted without actually deleting
        
    Returns:
        Number of files deleted (or would be deleted in dry-run mode)
    """
    # Calculate cutoff date
    cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).date()
    
    print(f"Pruning events older than {cutoff_date} (more than {days_to_keep} days ago)")
    print(f"Current date: {datetime.now().date()}")
    
    # Get old events
    old_events = get_old_events(events_dir, cutoff_date)
    
    if not old_events:
        print("No old events found to prune.")
        return 0
    
    # Sort for consistent output
    old_events.sort()
    
    print(f"\nFound {len(old_events)} old event(s):")
    for event_file in old_events:
        event_date = parse_date_from_filename(event_file.name)
        print(f"  - {event_file.name} (date: {event_date})")
    
    if dry_run:
        print(f"\nDry run - no files deleted")
        return len(old_events)
    
    # Delete the files
    deleted_count = 0
    print(f"\nDeleting old events...")
    for event_file in old_events:
        try:
            event_file.unlink()
            deleted_count += 1
            print(f"  ✓ Deleted {event_file.name}")
        except Exception as e:
            print(f"  ✗ Error deleting {event_file.name}: {e}")
    
    print(f"\nSuccessfully deleted {deleted_count} event file(s)")
    return deleted_count


def main():
    parser = argparse.ArgumentParser(
        description='Prune old events from the _single_events directory'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=DAYS_TO_KEEP,
        help=f'Number of days to keep events for (default: {DAYS_TO_KEEP})'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    parser.add_argument(
        '--events-dir',
        default=SINGLE_EVENTS_DIR,
        help=f'Path to events directory (default: {SINGLE_EVENTS_DIR})'
    )
    
    args = parser.parse_args()
    
    deleted_count = prune_events(
        events_dir=args.events_dir,
        days_to_keep=args.days,
        dry_run=args.dry_run
    )
    
    return 0 if deleted_count >= 0 else 1


if __name__ == '__main__':
    sys.exit(main())
