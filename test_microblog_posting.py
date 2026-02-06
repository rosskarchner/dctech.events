#!/usr/bin/env python3
"""
Tests for post_todays_events_to_microblog.py
"""
import unittest
from datetime import date
import sys
import os

# Import functions from the posting script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from post_todays_events_to_microblog import (
    get_events_for_date,
    is_virtual_event,
    get_week_url,
    create_post_text,
    CHAR_LIMIT,
)


class TestEventFiltering(unittest.TestCase):
    """Test event filtering"""
    
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
        ]
    
    def test_get_events_for_single_date(self):
        """Test filtering events for a single date"""
        target = date(2026, 1, 15)
        events = get_events_for_date(self.sample_events, target)
        
        # Should include: Python Meetup and Multi-Day Event
        self.assertEqual(len(events), 2)
        titles = [e['title'] for e in events]
        self.assertIn('Python Meetup', titles)
        self.assertIn('Multi-Day Event', titles)


class TestVirtualEventFiltering(unittest.TestCase):
    """Test virtual event detection"""
    
    def test_is_virtual_event_with_location_type(self):
        """Test that events with location_type='virtual' are identified as virtual"""
        event = {'title': 'Test Event', 'location_type': 'virtual'}
        self.assertTrue(is_virtual_event(event))
    
    def test_is_not_virtual_event_without_location_type(self):
        """Test that events without location_type field are not considered virtual"""
        event = {'title': 'Test Event', 'location': 'Washington, DC'}
        self.assertFalse(is_virtual_event(event))


class TestURLGeneration(unittest.TestCase):
    """Test week URL generation"""
    
    def test_get_week_url(self):
        """Test that week URL is generated correctly"""
        target = date(2026, 2, 6)  # Friday in week 6
        url = get_week_url(target)
        
        self.assertEqual(url, 'https://dctech.events/week/2026-W06/#2026-02-06')
    
    def test_get_week_url_different_week(self):
        """Test week URL for different week"""
        target = date(2026, 1, 5)  # Monday in week 2
        url = get_week_url(target)
        
        self.assertEqual(url, 'https://dctech.events/week/2026-W02/#2026-01-05')


class TestPostTextCreation(unittest.TestCase):
    """Test post text creation"""
    
    def test_create_post_text_three_events(self):
        """Test creating post text with three events"""
        events = [
            {'title': 'Cyberpunk Movie Night'},
            {'title': 'Diamond Gala'},
            {'title': 'Python Meetup'},
        ]
        target = date(2026, 2, 6)
        
        text = create_post_text(events, target)
        
        # Should use full list format
        self.assertIn('Cyberpunk Movie Night', text)
        self.assertIn('Diamond Gala', text)
        self.assertIn('Python Meetup', text)
        self.assertIn('https://dctech.events/week/2026-W06/#2026-02-06', text)
        self.assertLessEqual(len(text), CHAR_LIMIT)
        self.assertNotIn('and', text)  # Should not use "and N more" format
    
    def test_create_post_text_many_events(self):
        """Test creating post text with many events that require "and N more" format"""
        events = [
            {'title': 'Very Long Event Title That Takes Up A Tremendous Amount Of Space Number One'},
            {'title': 'Another Extremely Long Event Title That Takes Up Quite A Lot Of Space Too'},
            {'title': 'Yet Another Exceptionally Long Event Title For Our Comprehensive Testing Purposes'},
            {'title': 'Fourth Event With A Really Long Name'},
            {'title': 'Fifth Event Also With Long Name'},
            {'title': 'Sixth Event Continuing The Pattern'},
            {'title': 'Seventh Event'},
        ]
        target = date(2026, 2, 6)
        
        text = create_post_text(events, target)
        
        # Should use "and N more" format when events are too long
        # Just verify it stays under limit and has URL
        self.assertIn('https://dctech.events/week/2026-W06/#2026-02-06', text)
        self.assertLessEqual(len(text), CHAR_LIMIT)
    
    def test_create_post_text_single_event(self):
        """Test creating post text with single event"""
        events = [
            {'title': 'Python Meetup'},
        ]
        target = date(2026, 2, 6)
        
        text = create_post_text(events, target)
        
        self.assertIn('Python Meetup', text)
        self.assertIn('https://dctech.events/week/2026-W06/#2026-02-06', text)
        self.assertLessEqual(len(text), CHAR_LIMIT)
    
    def test_create_post_text_empty_list(self):
        """Test creating post text with empty event list"""
        events = []
        target = date(2026, 2, 6)
        
        text = create_post_text(events, target)
        
        self.assertIsNone(text)
    
    def test_create_post_text_character_limit(self):
        """Test that post text always stays under character limit"""
        # Create events with very long titles
        events = [
            {'title': 'A' * 200},
            {'title': 'B' * 200},
            {'title': 'C' * 200},
        ]
        target = date(2026, 2, 6)
        
        text = create_post_text(events, target)
        
        self.assertIsNotNone(text)
        self.assertLessEqual(len(text), CHAR_LIMIT)
        self.assertIn('https://dctech.events/week/2026-W06/#2026-02-06', text)
    
    def test_create_post_text_exact_format_three_events(self):
        """Test exact format for three events matches problem statement"""
        events = [
            {'title': 'Cyberpunk Movie Night'},
            {'title': 'Diamond Gala'},
            {'title': 'Python Meetup'},
        ]
        target = date(2026, 2, 6)
        
        text = create_post_text(events, target)
        
        # Should match example format from problem statement
        expected = 'DC Tech Events today: Cyberpunk Movie Night, Diamond Gala, Python Meetup  https://dctech.events/week/2026-W06/#2026-02-06'
        self.assertEqual(text, expected)
    
    def test_create_post_text_and_more_format(self):
        """Test "and N more" format matches problem statement pattern"""
        # Create events with titles that definitely won't all fit
        events = [
            {'title': 'A' * 80},  # Very long title
            {'title': 'B' * 80},  # Very long title
            {'title': 'C' * 80},  # Very long title
            {'title': 'D' * 80},  # Very long title
            {'title': 'E' * 80},  # Very long title
        ]
        target = date(2026, 2, 6)
        
        text = create_post_text(events, target)
        
        # Should use "and N more" format when titles are very long
        self.assertIn('and', text)
        self.assertIn('more', text)
        self.assertIn('DC Tech Events today:', text)
        self.assertIn('https://dctech.events/week/2026-W06/#2026-02-06', text)
        self.assertLessEqual(len(text), CHAR_LIMIT)


class TestFormatPreference(unittest.TestCase):
    """Test that format preference is respected"""
    
    def test_prefers_full_list_when_possible(self):
        """Test that full list format is preferred over 'and N more'"""
        # Create events that fit in full list
        events = [
            {'title': 'Event A'},
            {'title': 'Event B'},
            {'title': 'Event C'},
        ]
        target = date(2026, 2, 6)
        
        text = create_post_text(events, target)
        
        # Should not use "and more" format
        self.assertNotIn('and', text)
        self.assertNotIn('more', text)
        # Should list all events
        self.assertIn('Event A', text)
        self.assertIn('Event B', text)
        self.assertIn('Event C', text)
    
    def test_uses_and_more_when_necessary(self):
        """Test that 'and N more' format is used when full list doesn't fit"""
        # Create events with very long titles that definitely won't all fit
        events = [
            {'title': 'X' * 70},
            {'title': 'Y' * 70},
            {'title': 'Z' * 70},
            {'title': 'W' * 70},
            {'title': 'V' * 70},
        ]
        target = date(2026, 2, 6)
        
        text = create_post_text(events, target)
        
        # Should use "and more" format
        self.assertIn('and', text)
        self.assertIn('more', text)
        self.assertLessEqual(len(text), CHAR_LIMIT)


if __name__ == '__main__':
    unittest.main()
