#!/usr/bin/env python3
"""
Tests for post_to_mastodon.py and post_to_bluesky.py
"""
import unittest
import tempfile
import os
import yaml
from datetime import datetime, date
from pathlib import Path
import sys

# Import functions from the posting scripts
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from post_to_mastodon import (
    get_events_for_date,
    format_event_line,
    create_mastodon_post,
)
from post_to_bluesky import (
    get_events_for_date as get_events_for_date_bsky,
    format_event_line as format_event_line_bsky,
    create_bluesky_post,
)


class TestEventFiltering(unittest.TestCase):
    """Test event filtering for both scripts"""
    
    def setUp(self):
        """Set up test events"""
        self.sample_events = [
            {
                'title': 'Python Meetup',
                'date': '2026-01-15',
                'time': '18:30',
                'url': 'https://example.com/python'
            },
            {
                'title': 'JavaScript Conference',
                'date': '2026-01-16',
                'time': '09:00',
                'url': 'https://example.com/js'
            },
            {
                'title': 'Multi-Day Event',
                'date': '2026-01-15',
                'end_date': '2026-01-17',
                'url': 'https://example.com/multi'
            },
            {
                'title': 'All Day Event',
                'date': '2026-01-15',
                'url': 'https://example.com/allday'
            },
        ]
    
    def test_get_events_for_single_date(self):
        """Test filtering events for a single date"""
        target = date(2026, 1, 15)
        events = get_events_for_date(self.sample_events, target)
        
        # Should include: Python Meetup, Multi-Day Event, All Day Event
        self.assertEqual(len(events), 3)
        titles = [e['title'] for e in events]
        self.assertIn('Python Meetup', titles)
        self.assertIn('Multi-Day Event', titles)
        self.assertIn('All Day Event', titles)
        self.assertNotIn('JavaScript Conference', titles)
    
    def test_get_events_for_multi_day_middle(self):
        """Test filtering for middle day of multi-day event"""
        target = date(2026, 1, 16)
        events = get_events_for_date(self.sample_events, target)
        
        # Should include: JavaScript Conference and Multi-Day Event
        self.assertEqual(len(events), 2)
        titles = [e['title'] for e in events]
        self.assertIn('JavaScript Conference', titles)
        self.assertIn('Multi-Day Event', titles)
    
    def test_get_events_for_no_events_date(self):
        """Test filtering for date with no events"""
        target = date(2026, 1, 20)
        events = get_events_for_date(self.sample_events, target)
        self.assertEqual(len(events), 0)
    
    def test_bluesky_filter_consistency(self):
        """Ensure Bluesky filter works the same as Mastodon"""
        target = date(2026, 1, 15)
        mastodon_events = get_events_for_date(self.sample_events, target)
        bluesky_events = get_events_for_date_bsky(self.sample_events, target)
        self.assertEqual(len(mastodon_events), len(bluesky_events))


class TestEventFormatting(unittest.TestCase):
    """Test event formatting for both scripts"""
    
    def test_format_event_with_time(self):
        """Test formatting event with time"""
        event = {
            'title': 'Python Meetup',
            'time': '18:30',
        }
        result = format_event_line(event)
        self.assertIn('6:30pm', result)
        self.assertIn('Python Meetup', result)
        self.assertIn('•', result)
    
    def test_format_event_without_time(self):
        """Test formatting event without time"""
        event = {
            'title': 'All Day Event',
            'time': '',
        }
        result = format_event_line(event)
        self.assertIn('All Day Event', result)
        self.assertIn('•', result)
        self.assertNotIn('pm', result)
        self.assertNotIn('am', result)
    
    def test_format_event_truncation(self):
        """Test that long event titles are truncated"""
        event = {
            'title': 'A Very Long Event Title That Exceeds The Maximum Length Allowed For Display',
            'time': '10:00',
        }
        result = format_event_line(event, max_length=50)
        self.assertLessEqual(len(result), 50)
        self.assertIn('...', result)
    
    def test_format_event_dict_time(self):
        """Test formatting event with dict time (multi-day)"""
        event = {
            'title': 'Multi-Day Event',
            'time': {'2026-01-15': '10:00', '2026-01-16': '14:00'},
        }
        result = format_event_line(event)
        self.assertIn('Multi-Day Event', result)
        self.assertIn('•', result)
    
    def test_bluesky_format_shorter_max_length(self):
        """Test that Bluesky uses shorter max length by default"""
        event = {
            'title': 'Medium Length Event Title',
            'time': '10:00',
        }
        mastodon_result = format_event_line(event, max_length=100)
        bluesky_result = format_event_line_bsky(event, max_length=70)
        # Just ensure both work without error
        self.assertIn('Medium Length Event Title', mastodon_result)
        self.assertIn('Medium Length Event Title', bluesky_result)


class TestPostCreation(unittest.TestCase):
    """Test post creation for both platforms"""
    
    def setUp(self):
        """Set up test events and date"""
        self.events = [
            {
                'title': 'Event 1',
                'time': '18:00',
            },
            {
                'title': 'Event 2',
                'time': '19:00',
            },
            {
                'title': 'Event 3',
                'time': '',
            },
        ]
        self.target_date = date(2026, 1, 15)
        self.base_url = 'https://dctech.events'
    
    def test_mastodon_post_structure(self):
        """Test Mastodon post has correct structure"""
        post = create_mastodon_post(self.events, self.target_date, self.base_url)
        
        # Should contain emoji, date, events, and URL
        self.assertIn('📅', post)
        self.assertIn('January 15', post)
        self.assertIn('Event 1', post)
        self.assertIn('Event 2', post)
        self.assertIn('Event 3', post)
        self.assertIn(self.base_url, post)
    
    def test_bluesky_post_structure(self):
        """Test Bluesky post has correct structure"""
        post = create_bluesky_post(self.events, self.target_date, self.base_url)
        
        # Should contain emoji, shorter date, events, and URL
        self.assertIn('📅', post)
        self.assertIn('Jan 15', post)
        self.assertIn('Event 1', post)
        self.assertIn('Event 2', post)
        self.assertIn('Event 3', post)
        self.assertIn(self.base_url, post)
    
    def test_mastodon_post_length(self):
        """Test Mastodon post respects character limit"""
        # Create many events to test truncation
        many_events = [
            {'title': f'Event {i}', 'time': '10:00'}
            for i in range(20)
        ]
        post = create_mastodon_post(many_events, self.target_date, self.base_url)
        
        # Should be under 500 character limit
        self.assertLessEqual(len(post), 500)
        self.assertIn(self.base_url, post)
    
    def test_bluesky_post_length(self):
        """Test Bluesky post respects character limit"""
        # Create many events to test truncation
        many_events = [
            {'title': f'Event {i}', 'time': '10:00'}
            for i in range(20)
        ]
        post = create_bluesky_post(many_events, self.target_date, self.base_url)
        
        # Should be under 300 character limit
        self.assertLessEqual(len(post), 300)
        self.assertIn(self.base_url, post)
    
    def test_bluesky_shorter_than_mastodon(self):
        """Test that Bluesky posts are generally shorter due to limit"""
        post_mastodon = create_mastodon_post(self.events, self.target_date, self.base_url)
        post_bluesky = create_bluesky_post(self.events, self.target_date, self.base_url)
        
        # Bluesky should use abbreviated date and be more concise
        self.assertIn('January', post_mastodon)
        self.assertIn('Jan', post_bluesky)
        self.assertNotIn('January', post_bluesky)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases for both scripts"""
    
    def test_empty_event_list(self):
        """Test handling of empty event list"""
        events = []
        target_date = date(2026, 1, 15)
        base_url = 'https://dctech.events'
        
        # Should still create valid posts (though probably not useful)
        mastodon_post = create_mastodon_post(events, target_date, base_url)
        bluesky_post = create_bluesky_post(events, target_date, base_url)
        
        self.assertIn(base_url, mastodon_post)
        self.assertIn(base_url, bluesky_post)
    
    def test_event_without_title(self):
        """Test handling event without title"""
        event = {'time': '10:00'}
        result = format_event_line(event)
        self.assertIn('Untitled Event', result)
    
    def test_malformed_time(self):
        """Test handling of malformed time"""
        event = {
            'title': 'Test Event',
            'time': 'invalid',
        }
        result = format_event_line(event)
        # Should still include the title
        self.assertIn('Test Event', result)
    
    def test_events_with_special_characters(self):
        """Test events with special characters in title"""
        events = [
            {
                'title': 'C++ & Python: A Talk',
                'time': '18:00',
            },
            {
                'title': 'Event with "Quotes"',
                'time': '19:00',
            },
        ]
        target_date = date(2026, 1, 15)
        base_url = 'https://dctech.events'
        
        mastodon_post = create_mastodon_post(events, target_date, base_url)
        bluesky_post = create_bluesky_post(events, target_date, base_url)
        
        # Should handle special characters gracefully
        self.assertIn('C++', mastodon_post)
        self.assertIn('Quotes', bluesky_post)


if __name__ == '__main__':
    unittest.main()
