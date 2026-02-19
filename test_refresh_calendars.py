#!/usr/bin/env python3
"""
Tests for refresh_calendars.py to ensure event processing doesn't crash
"""
import unittest
import icalendar
from datetime import datetime, timedelta, timezone
import pytz
import re
from urllib.parse import urlparse
import recurring_ical_events

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
            parsed_url = urlparse(url)
            hostname = parsed_url.hostname or ''
            is_luma = (hostname == 'api.lu.ma' or 
                      hostname == 'api2.luma.com' or 
                      (hostname == 'luma.com' and '/ics' in parsed_url.path))
            self.assertTrue(is_luma, f"URL should be detected as lu.ma feed: {url}")
        
        # Test non-luma URLs
        non_luma_urls = [
            'https://example.com/calendar.ics',
            'https://meetup.com/events.ics',
            'https://evilapi2.luma.com.example.com/ics/get',  # Test malicious URL
        ]
        
        for url in non_luma_urls:
            parsed_url = urlparse(url)
            hostname = parsed_url.hostname or ''
            is_luma = (hostname == 'api.lu.ma' or 
                      hostname == 'api2.luma.com' or 
                      (hostname == 'luma.com' and '/ics' in parsed_url.path))
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

    def test_luma_description_url_extraction(self):
        """Test that lu.ma/luma.com URLs in the DESCRIPTION field are used as event URL"""
        cal = icalendar.Calendar()
        event = icalendar.Event()
        event.add('summary', 'Test Lu.ma Description Event')
        event.add('dtstart', datetime.now(pytz.UTC))
        event.add('dtend', datetime.now(pytz.UTC))
        event.add('description',
                  'Get up-to-date information at: https://luma.com/sfrx1dhi\n\n'
                  'Address:\nSTATION DC\nWashington, District of Columbia\n\n'
                  'Hosted by Sofia Wynn')
        cal.add_component(event)

        for component in cal.walk('VEVENT'):
            event_url = str(component.get('url', '')) if component.get('url') else None

            if not event_url:
                event_description = str(component.get('description', ''))
                url_match = re.search(r'https?://(?:lu\.ma|luma\.com)/[^\s\\]+', event_description)
                if url_match:
                    event_url = url_match.group(0)

            self.assertEqual(event_url, 'https://luma.com/sfrx1dhi',
                             "URL should be extracted from description field")

    def test_luma_description_url_not_used_when_url_field_present(self):
        """Test that explicit URL field takes priority over description URL"""
        cal = icalendar.Calendar()
        event = icalendar.Event()
        event.add('summary', 'Test Event')
        event.add('dtstart', datetime.now(pytz.UTC))
        event.add('dtend', datetime.now(pytz.UTC))
        event.add('url', 'https://lu.ma/explicit-url')
        event.add('description', 'Get up-to-date information at: https://luma.com/other-url')
        cal.add_component(event)

        for component in cal.walk('VEVENT'):
            event_url = str(component.get('url', '')) if component.get('url') else None

            if not event_url:
                event_description = str(component.get('description', ''))
                url_match = re.search(r'https?://(?:lu\.ma|luma\.com)/[^\s\\]+', event_description)
                if url_match:
                    event_url = url_match.group(0)

            self.assertEqual(event_url, 'https://lu.ma/explicit-url',
                             "Explicit URL field should take priority over description URL")

    def test_scan_for_metadata_default_true(self):
        """Test that scan_for_metadata defaults to True when not specified"""
        # No group - should default to True
        group = None
        scan_for_metadata = group.get('scan_for_metadata', True) if group else True
        self.assertTrue(scan_for_metadata, "scan_for_metadata should default to True when group is None")
        
        # Group without scan_for_metadata field - should default to True
        group = {'name': 'Test Group', 'ical': 'https://example.com/calendar.ics'}
        scan_for_metadata = group.get('scan_for_metadata', True)
        self.assertTrue(scan_for_metadata, "scan_for_metadata should default to True when not specified")

    def test_scan_for_metadata_false(self):
        """Test that scan_for_metadata can be set to False"""
        group = {
            'name': 'Test Group',
            'ical': 'https://example.com/calendar.ics',
            'scan_for_metadata': False
        }
        scan_for_metadata = group.get('scan_for_metadata', True)
        self.assertFalse(scan_for_metadata, "scan_for_metadata should be False when set to False")

    def test_scan_for_metadata_true(self):
        """Test that scan_for_metadata can be explicitly set to True"""
        group = {
            'name': 'Test Group',
            'ical': 'https://example.com/calendar.ics',
            'scan_for_metadata': True
        }
        scan_for_metadata = group.get('scan_for_metadata', True)
        self.assertTrue(scan_for_metadata, "scan_for_metadata should be True when set to True")

    def test_url_override_applied(self):
        """Test that url_override is applied when present"""
        group = {
            'name': 'Test Group',
            'url_override': 'https://example.com/meetings/'
        }
        event_url = 'https://example.com/event1'
        
        # Simulate the logic from refresh_calendars.py
        final_url = group.get('url_override') if group and group.get('url_override') else event_url
        
        self.assertEqual(final_url, 'https://example.com/meetings/',
                        "url_override should be used when present")

    def test_url_override_not_applied_when_absent(self):
        """Test that original event URL is used when url_override is not present"""
        group = {
            'name': 'Test Group',
            'ical': 'https://example.com/calendar.ics'
        }
        event_url = 'https://example.com/event1'
        
        # Simulate the logic from refresh_calendars.py
        final_url = group.get('url_override') if group and group.get('url_override') else event_url
        
        self.assertEqual(final_url, 'https://example.com/event1',
                        "original event URL should be used when url_override is not present")

    def test_url_override_with_none_group(self):
        """Test that original event URL is used when group is None"""
        group = None
        event_url = 'https://example.com/event1'
        
        # Simulate the logic from refresh_calendars.py
        final_url = group.get('url_override') if group and group.get('url_override') else event_url
        
        self.assertEqual(final_url, 'https://example.com/event1',
                        "original event URL should be used when group is None")

    def test_recurring_event_expansion(self):
        """Test that recurring events are expanded correctly"""
        # Create a sample iCal calendar with a recurring event
        cal = icalendar.Calendar()
        event = icalendar.Event()
        event.add('summary', 'Weekly Meeting')
        event.add('dtstart', datetime.now(timezone.utc))
        event.add('dtend', datetime.now(timezone.utc) + timedelta(hours=1))
        event.add('rrule', {'freq': 'weekly', 'count': 5})
        cal.add_component(event)
        
        # Expand recurring events for 60 days
        start_date = datetime.now(timezone.utc)
        end_date = start_date + timedelta(days=60)
        
        event_instances = list(recurring_ical_events.of(cal).between(start_date, end_date))
        
        # Should get at least 5 instances (the count specified in RRULE)
        # Note: the library may include the base event and recurrences
        self.assertGreaterEqual(len(event_instances), 5,
                        "Should expand to at least 5 instances based on RRULE count")
        
        # All instances should have the same summary
        for instance in event_instances:
            self.assertEqual(instance.get('summary'), 'Weekly Meeting',
                           "All instances should have the same summary")

    def test_non_recurring_event_handling(self):
        """Test that non-recurring events are still handled correctly"""
        # Create a sample iCal calendar with a non-recurring event
        cal = icalendar.Calendar()
        event = icalendar.Event()
        event.add('summary', 'One-time Event')
        event.add('dtstart', datetime.now(timezone.utc))
        event.add('dtend', datetime.now(timezone.utc) + timedelta(hours=1))
        cal.add_component(event)
        
        # Expand events for 60 days
        start_date = datetime.now(timezone.utc)
        end_date = start_date + timedelta(days=60)
        
        event_instances = list(recurring_ical_events.of(cal).between(start_date, end_date))
        
        # Should get exactly 1 instance for a non-recurring event
        self.assertEqual(len(event_instances), 1,
                        "Non-recurring event should have exactly 1 instance")
        
        # Verify it's the correct event
        self.assertEqual(event_instances[0].get('summary'), 'One-time Event',
                       "Event should have the correct summary")

if __name__ == '__main__':
    unittest.main()
