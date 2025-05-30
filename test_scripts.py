#!/usr/bin/env python3
import unittest
import os
import yaml
import responses
from datetime import datetime, timedelta, timezone
from add_meetup import validate_meetup_url, get_group_name_from_url, create_group_file, get_group_name_from_jsonld
from refresh_calendars import should_fetch

class TestRefreshCalendars(unittest.TestCase):
    def test_should_fetch_no_metadata(self):
        """Test that should_fetch returns True when no metadata exists"""
        self.assertTrue(should_fetch({}, 'test-group'))

    def test_should_fetch_old_data(self):
        """Test that should_fetch returns True when data is older than 4 hours"""
        old_time = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        meta_data = {'last_fetch': old_time}
        self.assertTrue(should_fetch(meta_data, 'test-group'))

    def test_should_fetch_recent_data(self):
        """Test that should_fetch returns False when data is less than 4 hours old"""
        recent_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        meta_data = {'last_fetch': recent_time}
        self.assertFalse(should_fetch(meta_data, 'test-group'))

class TestAddMeetup(unittest.TestCase):
    def setUp(self):
        # Create _groups directory if it doesn't exist
        os.makedirs('_groups', exist_ok=True)

    def test_validate_meetup_url_valid(self):
        """Test that valid meetup URLs are accepted."""
        valid_urls = [
            'https://www.meetup.com/dc-python-users-group/',
            'http://www.meetup.com/dc-python-users-group',
            'https://meetup.com/dc-python-users-group/'
        ]
        for url in valid_urls:
            self.assertTrue(validate_meetup_url(url))

    def test_validate_meetup_url_invalid(self):
        """Test that invalid URLs are rejected."""
        invalid_urls = [
            'https://example.com/group',
            'https://meetup.com/',
            'not-a-url',
            'https://www.meetup.com'
        ]
        for url in invalid_urls:
            with self.assertRaises(ValueError):
                validate_meetup_url(url)

    def test_get_group_name_from_url(self):
        """Test that group names are correctly extracted from URLs."""
        test_cases = [
            ('https://www.meetup.com/dc-python-users-group/', 'dc-python-users-group'),
            ('https://www.meetup.com/dc-python-users-group', 'dc-python-users-group'),
            ('http://meetup.com/test-group/', 'test-group'),
            ('https://www.meetup.com/novaopensourcecloud/', 'novaopensourcecloud'),
            ('https://www.meetup.com/dc-aws-users/', 'dc-aws-users')
        ]
        for url, expected in test_cases:
            self.assertEqual(get_group_name_from_url(url), expected)

    @responses.activate
    def test_get_group_name_from_jsonld(self):
        """Test extracting group name from JSON-LD data."""
        test_url = 'https://www.meetup.com/test-group/events/123/'
        test_html = """
        <html>
        <script type="application/ld+json">
        {
            "@context": "http://schema.org",
            "@type": "Event",
            "name": "Test Event",
            "organizer": {
                "@type": "Organization",
                "name": "Test Group Organization"
            }
        }
        </script>
        </html>
        """
        responses.add(responses.GET, test_url, body=test_html, status=200)
        
        # Test successful extraction
        self.assertEqual(get_group_name_from_jsonld(test_url), "Test Group Organization")
        
        # Test missing organization
        responses.reset()
        responses.add(responses.GET, test_url, body='<html></html>', status=200)
        with self.assertRaises(ValueError):
            get_group_name_from_jsonld(test_url)
        
        # Test network error
        responses.reset()
        responses.add(responses.GET, test_url, status=404)
        with self.assertRaises(ValueError):
            get_group_name_from_jsonld(test_url)

    @responses.activate
    def test_create_group_file(self):
        """Test that group files are created correctly."""
        test_cases = [
            ('https://www.meetup.com/test-group/', 'Test Group Organization', 'https://www.meetup.com/test-group'),
            ('https://www.meetup.com/dc-aws-users/', 'DC AWS Users Group', 'https://www.meetup.com/dc-aws-users'),
            ('https://www.meetup.com/novaopensourcecloud/', 'Nova Open Source Cloud', 'https://www.meetup.com/novaopensourcecloud')
        ]

        for test_url, expected_name, expected_clean_url in test_cases:
            test_file = f'_groups/{get_group_name_from_url(test_url)}.yaml'
            
            # Add mock response with JSON-LD data
            test_html = f"""
            <html>
            <script type="application/ld+json">
            {{
                "@context": "http://schema.org",
                "@type": "Event",
                "name": "Test Event",
                "organizer": {{
                    "@type": "Organization",
                    "name": "{expected_name}"
                }}
            }}
            </script>
            </html>
            """
            responses.add(responses.GET, test_url, body=test_html, status=200)

            try:
                # Remove test file if it exists
                if os.path.exists(test_file):
                    os.remove(test_file)

                # Create group file
                create_group_file(test_url)

                # Verify file was created
                self.assertTrue(os.path.exists(test_file))

                # Verify file contents
                with open(test_file, 'r') as f:
                    data = yaml.safe_load(f)
                    self.assertEqual(data['name'], expected_name)
                    self.assertEqual(data['website'], expected_clean_url)
                    self.assertEqual(data['rss'], expected_clean_url + '/events/rss')
                    self.assertTrue(data['active'])

            finally:
                # Cleanup
                if os.path.exists(test_file):
                    os.remove(test_file)
                responses.reset()

    def test_create_group_file_existing(self):
        """Test that creating a group file fails if it already exists."""
        test_url = 'https://www.meetup.com/test-group/'
        test_file = '_groups/test-group.yaml'

        try:
            # Create initial file
            create_group_file(test_url)

            # Try to create it again
            with self.assertRaises(SystemExit):
                create_group_file(test_url)

        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)

class TestEventProcessing(unittest.TestCase):
    def test_looks_like_url(self):
        """Test that URLs are correctly identified"""
        from generate_month_data import looks_like_url
        
        # Test valid URLs
        valid_urls = [
            'http://example.com',
            'https://example.com',
            'www.example.com',
            'https://www.example.com/path',
            'http://subdomain.example.com/path?param=value'
        ]
        for url in valid_urls:
            self.assertTrue(looks_like_url(url), f"Should identify {url} as URL")
        
        # Test invalid URLs
        invalid_urls = [
            '',
            None,
            'Just some text',
            '123 Main St, City',
            'example.com',  # No www or http(s)
            'Virtual Event'
        ]
        for url in invalid_urls:
            self.assertFalse(looks_like_url(url), f"Should not identify {url} as URL")
    
    def test_event_url_from_location(self):
        """Test that location field is used as URL when appropriate"""
        from generate_month_data import event_to_dict
        from icalendar import Event
        from datetime import datetime
        import pytz
        
        # Create a basic event
        event = Event()
        event.add('summary', 'Test Event')
        event.add('dtstart', datetime.now(pytz.UTC))
        event.add('dtend', datetime.now(pytz.UTC) + timedelta(hours=1))
        
        # Test case 1: Location is a URL, no explicit URL
        event['location'] = 'https://zoom.us/j/123456789'
        result = event_to_dict(event)
        self.assertEqual(result['url'], 'https://zoom.us/j/123456789')
        self.assertEqual(result['location'], '')  # Location should be cleared
        
        # Test case 2: Location is a URL but explicit URL exists
        event['url'] = 'https://example.com/event'
        event['location'] = 'https://zoom.us/j/123456789'
        result = event_to_dict(event)
        self.assertEqual(result['url'], 'https://example.com/event')  # Should use explicit URL
        self.assertEqual(result['location'], 'https://zoom.us/j/123456789')  # Location should remain
        
        # Test case 3: Location is not a URL
        event['url'] = ''
        event['location'] = '123 Main St, City'
        result = event_to_dict(event)
        self.assertIsNone(result)  # Should return None as no URL is available
        
        # Test case 4: Location is not a URL but group has fallback URL
        group = {'name': 'Test Group', 'fallback_url': 'https://example.com/group'}
        result = event_to_dict(event, group)
        self.assertEqual(result['url'], 'https://example.com/group')
        self.assertEqual(result['location'], '123 Main St, City')
    
    def test_today_variable_in_generate_yaml(self):
        """Test that the 'today' variable is properly defined in generate_yaml"""
        import os
        from datetime import datetime, date
        import pytz
        from generate_month_data import generate_yaml, local_tz
        
        # Create necessary directories
        os.makedirs('_data', exist_ok=True)
        os.makedirs('_groups', exist_ok=True)
        os.makedirs('_single_events', exist_ok=True)
        
        try:
            # Run generate_yaml
            result = generate_yaml()
            
            # If we get here without an UnboundLocalError, the test passes
            self.assertTrue(result)
            
        except UnboundLocalError as e:
            self.fail(f"generate_yaml raised UnboundLocalError: {e}")
        finally:
            # Clean up any files created during the test
            if os.path.exists('_data/upcoming.yaml'):
                os.remove('_data/upcoming.yaml')
            if os.path.exists('_data/stats.yaml'):
                os.remove('_data/stats.yaml')

class TestStatsGeneration(unittest.TestCase):
    def test_calculate_stats(self):
        """Test that stats are calculated correctly"""
        from generate_month_data import calculate_stats
        from datetime import datetime, timedelta
        import pytz
        
        # Get current date for testing
        today = datetime.now(pytz.timezone('US/Eastern')).date()
        yesterday = (today - timedelta(days=1)).strftime('%Y-%m-%d')
        tomorrow = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        next_month = (today + timedelta(days=40)).strftime('%Y-%m-%d')
        
        # Test with empty data
        stats = calculate_stats([], [])
        self.assertEqual(stats['upcoming_events'], 0)
        self.assertEqual(stats['active_groups'], 0)
        
        # Test with some groups and events
        groups = [
            {'name': 'Group 1', 'active': True},
            {'name': 'Group 2', 'active': True},
            {'name': 'Group 3', 'active': False}
        ]
        
        events = [
            {'title': 'Past Event', 'date': yesterday},
            {'title': 'Tomorrow Event', 'date': tomorrow},
            {'title': 'Next Month Event', 'date': next_month}
        ]
        
        stats = calculate_stats(groups, events)
        self.assertEqual(stats['upcoming_events'], 2)  # Only future events
        self.assertEqual(stats['active_groups'], 2)

class TestMonthlyYamlGeneration(unittest.TestCase):
    def test_skip_current_and_next_month(self):
        """Test that monthly YAML files skip current and next months"""
        import os
        from datetime import datetime, date, timedelta
        import pytz
        from generate_month_data import generate_yaml, local_tz
        
        # Create necessary directories
        os.makedirs('_data', exist_ok=True)
        os.makedirs('_groups', exist_ok=True)
        os.makedirs('_single_events', exist_ok=True)
        
        # Create a test event file
        test_event = {
            'title': 'Test Event',
            'date': '2025-05-31',  # Current month
            'time': '10:00',
            'url': 'https://example.com',
            'location': 'Test Location'
        }
        
        test_event_file = '_single_events/test_event.yaml'
        try:
            with open(test_event_file, 'w') as f:
                yaml.dump(test_event, f)
            
            # Run generate_yaml
            result = generate_yaml()
            self.assertTrue(result)
            
            # Check that May 2025 and June 2025 files were not created
            may_file = '_data/2025_may.yaml'
            june_file = '_data/2025_june.yaml'
            july_file = '_data/2025_july.yaml'
            
            self.assertFalse(os.path.exists(may_file), "May 2025 file should not exist")
            self.assertFalse(os.path.exists(june_file), "June 2025 file should not exist")
            # July file may or may not exist depending on if there are events
            
        finally:
            # Clean up test files
            if os.path.exists(test_event_file):
                os.remove(test_event_file)
            for file in [may_file, june_file, july_file]:
                if os.path.exists(file):
                    os.remove(file)

class TestSuppressUrls(unittest.TestCase):
    def test_suppress_urls(self):
        """Test that events with URLs in suppress_urls list are ignored"""
        from generate_month_data import event_to_dict, generate_yaml
        from icalendar import Event
        from datetime import datetime
        import pytz
        import os
        
        # Create necessary directories
        os.makedirs('_data', exist_ok=True)
        os.makedirs('_groups', exist_ok=True)
        os.makedirs('_cache/ical', exist_ok=True)
        
        # Create a test group with suppress_urls
        group = {
            'name': 'Test Group',
            'website': 'https://example.com',
            'suppress_urls': ['https://example.com/suppressed']
        }
        
        # Create a basic event that should be suppressed
        event = Event()
        event.add('summary', 'Test Event')
        event.add('dtstart', datetime.now(pytz.UTC))
        event.add('dtend', datetime.now(pytz.UTC) + timedelta(hours=1))
        event.add('url', 'https://example.com/suppressed')
        
        # Test that event_to_dict works but event is filtered out
        result = event_to_dict(event, group)
        self.assertIsNotNone(result)
        self.assertEqual(result['url'], 'https://example.com/suppressed')
        
        # Create test group file
        group_file = '_groups/test_group.yaml'
        with open(group_file, 'w') as f:
            yaml.dump(group, f)
            
        # Create test calendar file with the event
        calendar = icalendar.Calendar()
        calendar.add_component(event)
        cache_file = '_cache/ical/test_group.ics'
        with open(cache_file, 'w') as f:
            f.write(calendar.to_ical().decode('utf-8'))
            
        try:
            # Run generate_yaml
            generate_yaml()
            
            # Check that the event was not included in upcoming.yaml
            with open('_data/upcoming.yaml', 'r') as f:
                upcoming_events = yaml.safe_load(f)
                self.assertTrue(isinstance(upcoming_events, list))
                # Verify the suppressed event is not in the list
                suppressed_events = [e for e in upcoming_events if e['url'] == 'https://example.com/suppressed']
                self.assertEqual(len(suppressed_events), 0)
                
        finally:
            # Clean up test files
            for file in [group_file, cache_file, '_data/upcoming.yaml', '_data/stats.yaml']:
                if os.path.exists(file):
                    os.remove(file)

class TestFutureEventLimit(unittest.TestCase):
    def test_future_event_limit(self):
        """Test that aggregated events more than 90 days in the future are excluded,
        but single events beyond 90 days are included"""
        import os
        from datetime import datetime, timedelta
        import pytz
        import icalendar
        from generate_month_data import generate_yaml, local_tz
        
        # Create necessary directories
        os.makedirs('_data', exist_ok=True)
        os.makedirs('_groups', exist_ok=True)
        os.makedirs('_single_events', exist_ok=True)
        os.makedirs('_cache/ical', exist_ok=True)
        
        # Get current date
        today = datetime.now(local_tz).date()
        
        # Create test single events at different future dates
        test_single_events = [
            {
                'title': 'Tomorrow Single Event',
                'date': (today + timedelta(days=1)).strftime('%Y-%m-%d'),
                'time': '10:00',
                'url': 'https://example.com/tomorrow-single'
            },
            {
                'title': '91 Days Single Event',
                'date': (today + timedelta(days=91)).strftime('%Y-%m-%d'),
                'time': '10:00',
                'url': 'https://example.com/91days-single'
            }
        ]
        
        # Create test group and iCal events
        test_group = {
            'name': 'Test Group',
            'website': 'https://example.com',
            'ical': 'https://example.com/calendar.ics'
        }
        
        # Create iCal calendar with events
        calendar = icalendar.Calendar()
        
        # Add tomorrow event
        event1 = icalendar.Event()
        event1.add('summary', 'Tomorrow iCal Event')
        event1.add('dtstart', datetime.now(pytz.UTC) + timedelta(days=1))
        event1.add('dtend', datetime.now(pytz.UTC) + timedelta(days=1, hours=1))
        event1.add('url', 'https://example.com/tomorrow-ical')
        calendar.add_component(event1)
        
        # Add 91 days event
        event2 = icalendar.Event()
        event2.add('summary', '91 Days iCal Event')
        event2.add('dtstart', datetime.now(pytz.UTC) + timedelta(days=91))
        event2.add('dtend', datetime.now(pytz.UTC) + timedelta(days=91, hours=1))
        event2.add('url', 'https://example.com/91days-ical')
        calendar.add_component(event2)
        
        try:
            # Create test single event files
            for i, event in enumerate(test_single_events):
                with open(f'_single_events/test_event_{i}.yaml', 'w') as f:
                    yaml.dump(event, f)
            
            # Create test group file
            with open('_groups/test_group.yaml', 'w') as f:
                yaml.dump(test_group, f)
                
            # Create test iCal cache file
            with open('_cache/ical/test_group.ics', 'w') as f:
                f.write(calendar.to_ical().decode('utf-8'))
            
            # Run generate_yaml
            generate_yaml()
            
            # Check upcoming.yaml
            with open('_data/upcoming.yaml', 'r') as f:
                upcoming_events = yaml.safe_load(f)
                
            # Get all event URLs
            event_urls = [e['url'] for e in upcoming_events]
            
            # Verify single events are included regardless of date
            self.assertIn('https://example.com/tomorrow-single', event_urls, "Tomorrow's single event should be included")
            self.assertIn('https://example.com/91days-single', event_urls, "91-day future single event should be included")
            
            # Verify iCal events follow the 90-day limit
            self.assertIn('https://example.com/tomorrow-ical', event_urls, "Tomorrow's iCal event should be included")
            self.assertNotIn('https://example.com/91days-ical', event_urls, "91-day future iCal event should be excluded")
            
        finally:
            # Clean up test files
            for i in range(len(test_single_events)):
                if os.path.exists(f'_single_events/test_event_{i}.yaml'):
                    os.remove(f'_single_events/test_event_{i}.yaml')
            if os.path.exists('_groups/test_group.yaml'):
                os.remove('_groups/test_group.yaml')
            if os.path.exists('_cache/ical/test_group.ics'):
                os.remove('_cache/ical/test_group.ics')
            if os.path.exists('_data/upcoming.yaml'):
                os.remove('_data/upcoming.yaml')
            if os.path.exists('_data/stats.yaml'):
                os.remove('_data/stats.yaml')

if __name__ == '__main__':
    unittest.main()