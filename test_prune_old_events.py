#!/usr/bin/env python3
"""
Tests for prune_old_events.py
"""
import unittest
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta
from prune_old_events import parse_date_from_filename, get_old_events, prune_events


class TestPruneOldEvents(unittest.TestCase):
    
    def test_parse_date_from_filename_valid(self):
        """Test parsing valid date from filename"""
        filename = "2025-12-05-test-event.yaml"
        result = parse_date_from_filename(filename)
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 12)
        self.assertEqual(result.day, 5)
    
    def test_parse_date_from_filename_with_special_chars(self):
        """Test parsing date from filename with special characters"""
        filename = "2025-06-10-aws-summit-washington,-dc-2025.yaml"
        result = parse_date_from_filename(filename)
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 6)
        self.assertEqual(result.day, 10)
    
    def test_parse_date_from_filename_invalid_format(self):
        """Test parsing invalid filename format"""
        filename = "invalid-filename.yaml"
        result = parse_date_from_filename(filename)
        self.assertIsNone(result)
    
    def test_parse_date_from_filename_no_date(self):
        """Test parsing filename without date"""
        filename = "cybertalks_2025.yaml"
        result = parse_date_from_filename(filename)
        self.assertIsNone(result)
    
    def test_parse_date_from_filename_invalid_date(self):
        """Test parsing filename with invalid date values"""
        filename = "2025-13-45-invalid-event.yaml"
        result = parse_date_from_filename(filename)
        self.assertIsNone(result)
    
    def test_get_old_events_with_temp_directory(self):
        """Test getting old events from a temporary directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some test event files
            old_date = (datetime.now() - timedelta(days=10)).date()
            recent_date = (datetime.now() - timedelta(days=3)).date()
            
            old_file = Path(tmpdir) / f"{old_date}-old-event.yaml"
            recent_file = Path(tmpdir) / f"{recent_date}-recent-event.yaml"
            no_date_file = Path(tmpdir) / "no-date-event.yaml"
            
            old_file.touch()
            recent_file.touch()
            no_date_file.touch()
            
            # Get old events with 7 day cutoff
            cutoff_date = (datetime.now() - timedelta(days=7)).date()
            old_events = get_old_events(tmpdir, cutoff_date)
            
            # Should only find the old event
            self.assertEqual(len(old_events), 1)
            self.assertEqual(old_events[0].name, old_file.name)
    
    def test_get_old_events_empty_directory(self):
        """Test getting old events from an empty directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cutoff_date = (datetime.now() - timedelta(days=7)).date()
            old_events = get_old_events(tmpdir, cutoff_date)
            self.assertEqual(len(old_events), 0)
    
    def test_prune_events_dry_run(self):
        """Test pruning events in dry-run mode"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create an old event file
            old_date = (datetime.now() - timedelta(days=10)).date()
            old_file = Path(tmpdir) / f"{old_date}-old-event.yaml"
            old_file.touch()
            
            # Run in dry-run mode
            deleted_count = prune_events(events_dir=tmpdir, days_to_keep=7, dry_run=True)
            
            # Should report 1 file to delete
            self.assertEqual(deleted_count, 1)
            # But file should still exist
            self.assertTrue(old_file.exists())
    
    def test_prune_events_actual_deletion(self):
        """Test actually deleting old events"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create old and recent event files
            old_date = (datetime.now() - timedelta(days=10)).date()
            recent_date = (datetime.now() - timedelta(days=3)).date()
            
            old_file = Path(tmpdir) / f"{old_date}-old-event.yaml"
            recent_file = Path(tmpdir) / f"{recent_date}-recent-event.yaml"
            
            old_file.touch()
            recent_file.touch()
            
            # Run pruning
            deleted_count = prune_events(events_dir=tmpdir, days_to_keep=7, dry_run=False)
            
            # Should delete 1 file
            self.assertEqual(deleted_count, 1)
            # Old file should be deleted
            self.assertFalse(old_file.exists())
            # Recent file should still exist
            self.assertTrue(recent_file.exists())
    
    def test_prune_events_custom_days(self):
        """Test pruning with custom days to keep"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create events at different ages
            event_5_days = (datetime.now() - timedelta(days=5)).date()
            event_15_days = (datetime.now() - timedelta(days=15)).date()
            
            file_5 = Path(tmpdir) / f"{event_5_days}-recent-event.yaml"
            file_15 = Path(tmpdir) / f"{event_15_days}-old-event.yaml"
            
            file_5.touch()
            file_15.touch()
            
            # Prune with 10 day retention
            deleted_count = prune_events(events_dir=tmpdir, days_to_keep=10, dry_run=False)
            
            # Should only delete the 15-day old event
            self.assertEqual(deleted_count, 1)
            self.assertTrue(file_5.exists())
            self.assertFalse(file_15.exists())


if __name__ == '__main__':
    unittest.main()
