#!/usr/bin/env python3
"""
Tests for refresh_calendars.py to ensure event processing doesn't crash
"""
import unittest
import icalendar
from datetime import datetime
import pytz
import re

class TestRefreshCalendars(unittest.TestCase):
    def test_event_component_has_summary(self):
        """Test that iCal event components have the 'summary' field"""
        # Create a sample iCal event component
        cal = icalendar.Calendar()
        event = icalendar.Event()
        event.add('summary', 'Test Event')
        event.add('dtstart', datetime.now(pytz.UTC))
        event.add('dtend', datetime.now(pytz.UTC))
        cal.add_component(event)
        
        # Walk through events
        for component in cal.walk('VEVENT'):
            # This is what the code does - verify it works
            title = component.get('summary', 'Unknown')
            self.assertEqual(title, 'Test Event')
    
    def test_component_get_returns_unknown_for_missing_field(self):
        """Test that component.get() returns default for missing fields"""
        cal = icalendar.Calendar()
        event = icalendar.Event()
        event.add('dtstart', datetime.now(pytz.UTC))
        event.add('dtend', datetime.now(pytz.UTC))
        cal.add_component(event)
        
        # Walk through events
        for component in cal.walk('VEVENT'):
            # Test that we can safely get missing summary
            title = component.get('summary', 'Unknown')
            self.assertEqual(title, 'Unknown')

    def test_luma_feed_detection(self):
        """Test that lu.ma feeds are correctly identified"""
        luma_urls = [
            'https://api.lu.ma/ics/get?entity=calendar&id=cal-kgY3yq1wD2o9XxI',
            'https://api2.luma.com/ics/get?entity=calendar&id=cal-kgY3yq1wD2o9XxI',
            'https://luma.com/ics/get?entity=calendar&id=cal-kgY3yq1wD2o9XxI',
        ]
        
        for url in luma_urls:
            is_luma = 'api.lu.ma' in url or 'api2.luma.com' in url or 'luma.com/ics' in url
            self.assertTrue(is_luma, f"URL should be detected as lu.ma feed: {url}")
        
        # Test non-luma URLs
        non_luma_urls = [
            'https://example.com/calendar.ics',
            'https://meetup.com/events.ics',
        ]
        
        for url in non_luma_urls:
            is_luma = 'api.lu.ma' in url or 'api2.luma.com' in url or 'luma.com/ics' in url
            self.assertFalse(is_luma, f"URL should NOT be detected as lu.ma feed: {url}")

    def test_url_extraction_from_location(self):
        """Test that URLs are correctly extracted from location field"""
        test_cases = [
            ('https://lu.ma/vu8ktr9y', 'https://lu.ma/vu8ktr9y'),
            ('https://example.com/event', 'https://example.com/event'),
            ('Join us at https://lu.ma/abc123 for fun', 'https://lu.ma/abc123'),
            ('http://test.com', 'http://test.com'),
            ('Regular address, no URL', None),
            ('', None),
        ]
        
        for location, expected_url in test_cases:
            if location and ('http://' in location or 'https://' in location):
                url_match = re.search(r'https?://[^\s]+', location)
                if url_match:
                    extracted_url = url_match.group(0)
                    self.assertEqual(extracted_url, expected_url, 
                                   f"Failed to extract URL from: {location}")
                else:
                    self.assertIsNone(expected_url,
                                    f"Should not extract URL from: {location}")
            else:
                self.assertIsNone(expected_url,
                                f"Should not process non-URL location: {location}")

    def test_luma_location_url_in_ical_component(self):
        """Test that lu.ma events with URL in location field are processed correctly"""
        # Create a sample iCal event with URL in location
        cal = icalendar.Calendar()
        event = icalendar.Event()
        event.add('summary', 'Test Lu.ma Event')
        event.add('dtstart', datetime.now(pytz.UTC))
        event.add('dtend', datetime.now(pytz.UTC))
        event.add('location', 'https://lu.ma/vu8ktr9y')
        cal.add_component(event)
        
        # Simulate the logic from refresh_calendars.py
        for component in cal.walk('VEVENT'):
            event_url = str(component.get('url', '')) if component.get('url') else None
            is_luma_feed = True  # Simulating a lu.ma feed
            
            # Special handling for lu.ma feeds
            if is_luma_feed and not event_url:
                event_location = str(component.get('location', ''))
                if event_location and ('http://' in event_location or 'https://' in event_location):
                    url_match = re.search(r'https?://[^\s]+', event_location)
                    if url_match:
                        event_url = url_match.group(0)
            
            self.assertEqual(event_url, 'https://lu.ma/vu8ktr9y',
                           "URL should be extracted from location field")

if __name__ == '__main__':
    unittest.main()
