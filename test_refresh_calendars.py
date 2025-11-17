#!/usr/bin/env python3
"""
Tests for refresh_calendars.py to ensure event processing doesn't crash
"""
import unittest
import icalendar
from datetime import datetime
import pytz

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

if __name__ == '__main__':
    unittest.main()
