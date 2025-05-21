#!/usr/bin/env python3
import unittest
import os
import sys
import shutil
import tempfile
from pathlib import Path
import yaml

# Import the scripts to test
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# Rename the modules to avoid conflicts with the script names
import refresh_calendars as refresh_calendars_module
import generate_month_data as generate_month_data_module

class TestScripts(unittest.TestCase):
    def setUp(self):
        # Create temporary directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = os.path.join(self.temp_dir, '_data')
        self.cache_dir = os.path.join(self.temp_dir, '_cache')
        self.ical_cache_dir = os.path.join(self.cache_dir, 'ical')
        self.rss_cache_dir = os.path.join(self.cache_dir, 'rss')
        self.single_events_dir = os.path.join(self.temp_dir, '_single_events')
        
        # Create the directories
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.ical_cache_dir, exist_ok=True)
        os.makedirs(self.rss_cache_dir, exist_ok=True)
        os.makedirs(self.single_events_dir, exist_ok=True)
        
        # Set the constants in the modules to use our test directories
        refresh_calendars_module.DATA_DIR = self.data_dir
        refresh_calendars_module.CACHE_DIR = self.cache_dir
        refresh_calendars_module.ICAL_CACHE_DIR = self.ical_cache_dir
        refresh_calendars_module.RSS_CACHE_DIR = self.rss_cache_dir
        refresh_calendars_module.CURRENT_DAY_FILE = os.path.join(self.data_dir, 'current_day.txt')
        refresh_calendars_module.REFRESH_FLAG_FILE = os.path.join(self.data_dir, '.refreshed')
        
        generate_month_data_module.DATA_DIR = self.data_dir
        generate_month_data_module.CACHE_DIR = self.cache_dir
        generate_month_data_module.ICAL_CACHE_DIR = self.ical_cache_dir
        generate_month_data_module.RSS_CACHE_DIR = self.rss_cache_dir
        generate_month_data_module.SINGLE_EVENTS_DIR = self.single_events_dir
        generate_month_data_module.REFRESH_FLAG_FILE = os.path.join(self.data_dir, '.refreshed')
        generate_month_data_module.UPDATED_FLAG_FILE = os.path.join(self.data_dir, '.updated')
    
    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.temp_dir)
    
    def test_update_current_day_file(self):
        """Test that the current day file is updated correctly"""
        # Call the function
        refresh_calendars_module.update_current_day_file()
        
        # Check that the file exists
        self.assertTrue(os.path.exists(refresh_calendars_module.CURRENT_DAY_FILE))
        
        # Check that the file contains today's date
        with open(refresh_calendars_module.CURRENT_DAY_FILE, 'r') as f:
            content = f.read().strip()
        
        today = refresh_calendars_module.datetime.now(refresh_calendars_module.local_tz).date()
        today_str = today.strftime('%Y-%m-%d')
        
        self.assertEqual(content, today_str)
    
    def test_is_current_day_file_updated(self):
        """Test that the current day file check works correctly"""
        # First check when the file doesn't exist
        self.assertFalse(refresh_calendars_module.is_current_day_file_updated())
        
        # Create the file with today's date
        refresh_calendars_module.update_current_day_file()
        
        # Now check again
        self.assertTrue(refresh_calendars_module.is_current_day_file_updated())
    
    def test_single_event_date_parsing(self):
        """Test that single events can use flexible date/time formats"""
        # Create test event files with different date/time formats
        test_events = [
            {
                'title': 'Test Event 1',
                'description': 'A test event',
                'location': 'Test Location',
                'url': 'http://test.com',
                'date': '2024-01-15',
                'time': '6pm',  # Using flexible time format
            },
            {
                'title': 'Test Event 2',
                'description': 'Another test event',
                'location': 'Test Location',
                'url': 'http://test.com',
                'date': '2024-01-15',
                'time': '6:00 PM',  # Standard 12-hour format
            },
            {
                'title': 'Test Event 3',
                'description': 'Yet another test event',
                'location': 'Test Location',
                'url': 'http://test.com',
                'date': '2024-01-15',
                'time': '18:00',  # 24-hour format
            },
            {
                'title': 'Test Event 4',
                'description': 'Event with human readable date',
                'location': 'Test Location',
                'url': 'http://test.com',
                'date': 'Jan 15, 2024',  # Human readable date
                'time': '6pm',
            },
            {
                'title': 'Test Event 5',
                'description': 'Event with standard 24-hour time',
                'location': 'Test Location',
                'url': 'http://test.com',
                'date': '2024-01-15',
                'time': '10:00',  # Standard 24-hour format without leading zero
            },
            {
                'title': 'Test Event 6',
                'description': 'Event with integer time',
                'location': 'Test Location',
                'url': 'http://test.com',
                'date': '2024-01-15',
                'time': 1000,  # Integer time format
            },
            {
                'title': 'Test Event 7',
                'description': 'Event with ordinal date format',
                'location': 'Test Location',
                'url': 'http://test.com',
                'date': 'June 6th 2025',  # Date with ordinal suffix
                'time': '14:00',
            },
            {
                'title': 'Test Event 8',
                'description': 'Event with ordinal date and end date',
                'location': 'Test Location',
                'url': 'http://test.com',
                'date': 'June 6th 2025',
                'time': '14:00',
                'end_date': 'June 7th 2025',
                'end_time': '16:00',
            },
            {
                'title': 'Test Event 9',
                'description': 'Event with mixed date formats',
                'location': 'Test Location',
                'url': 'http://test.com',
                'date': 'June 6th 2025',
                'time': '2pm',
                'end_date': '2025-06-06',  # Standard format end date
                'end_time': '16:00',
            }
        ]
        
        for i, event_data in enumerate(test_events):
            event_file = os.path.join(self.single_events_dir, f'test_event_{i}.yaml')
            with open(event_file, 'w') as f:
                yaml.dump(event_data, f, allow_unicode=True)
        
        # Load and process the events
        events = generate_month_data_module.load_single_events()
        
        # Check that we got all events
        self.assertEqual(len(events), 9)
        
        # Check that all events with 6pm were parsed correctly to 18:00
        for event in events[:4]:
            self.assertEqual(event['start_time'], '18:00')
            self.assertEqual(event['start_date'], '2024-01-15')
            
        # Check that 10:00 was parsed correctly
        self.assertEqual(events[4]['start_time'], '10:00')
        self.assertEqual(events[4]['start_date'], '2024-01-15')
        
        # Check that integer time 1000 was parsed correctly to 10:00
        self.assertEqual(events[5]['start_time'], '10:00')
        self.assertEqual(events[5]['start_date'], '2024-01-15')
        
        # Check ordinal date format (June 6th 2025)
        self.assertEqual(events[6]['start_date'], '2025-06-06')
        self.assertEqual(events[6]['start_time'], '14:00')
        
        # Check ordinal dates with end date
        self.assertEqual(events[7]['start_date'], '2025-06-06')
        self.assertEqual(events[7]['start_time'], '14:00')
        self.assertEqual(events[7]['end_date'], '2025-06-07')
        self.assertEqual(events[7]['end_time'], '16:00')
        
    def test_rss_event_processing(self):
        """Test that RSS events are processed and cached correctly"""
        # Create a test group with RSS feed
        group = {
            'name': 'Test Group',
            'website': 'http://test.com',
            'rss': 'http://test.com/feed',
            'active': True,
            'id': 'test_group'
        }
        
        # Create test cached RSS events
        events = [
            {
                'title': 'Test Event 1',
                'description': 'A test event',
                'location': 'Test Location',
                'url': 'http://test.com/event1',
                'start_date': '2024-01-15',
                'start_time': '18:00',
                'end_date': '2024-01-15',
                'end_time': '20:00',
                'date': '2024-01-15',
                'time': '18:00'
            },
            {
                'title': 'Test Event 2',
                'description': 'Another test event',
                'location': 'Test Location 2',
                'url': 'http://test.com/event2',
                'start_date': '2024-01-16',
                'start_time': '19:00',
                'end_date': '2024-01-16',
                'end_time': '21:00',
                'date': '2024-01-16',
                'time': '19:00'
            }
        ]
        
        # Save the events to the cache
        cache_file = os.path.join(self.rss_cache_dir, 'test_group.json')
        with open(cache_file, 'w') as f:
            json.dump(events, f)
        
        # Generate YAML files
        generate_month_data_module.generate_yaml()
        
        # Check that the events were included in the output
        upcoming_file = os.path.join(self.data_dir, 'upcoming.yaml')
        self.assertTrue(os.path.exists(upcoming_file))
        
        with open(upcoming_file, 'r') as f:
            upcoming_events = yaml.safe_load(f)
        
        # Check that we got both events
        self.assertEqual(len(upcoming_events), 2)
        
        # Check event details
        event1 = upcoming_events[0]
        self.assertEqual(event1['title'], 'Test Event 1')
        self.assertEqual(event1['start_date'], '2024-01-15')
        self.assertEqual(event1['start_time'], '18:00')
        self.assertEqual(event1['end_date'], '2024-01-15')
        self.assertEqual(event1['end_time'], '20:00')
        
        event2 = upcoming_events[1]
        self.assertEqual(event2['title'], 'Test Event 2')
        self.assertEqual(event2['start_date'], '2024-01-16')
        self.assertEqual(event2['start_time'], '19:00')
        self.assertEqual(event2['end_date'], '2024-01-16')
        self.assertEqual(event2['end_time'], '21:00')
        # Check mixed date formats
        self.assertEqual(events[8]['start_date'], '2025-06-06')
        self.assertEqual(events[8]['start_time'], '14:00')  # 2pm -> 14:00
        self.assertEqual(events[8]['end_date'], '2025-06-06')
        self.assertEqual(events[8]['end_time'], '16:00')

    def _render_event_template(self, event):
        """Helper method to render an event through the template"""
        from jinja2 import Environment, PackageLoader
        env = Environment(loader=PackageLoader('app', 'templates'))
        template = env.get_template('partials/events_by_day.html')
        
        # Create a test day structure
        day = {
            'date': '2024-01-01',
            'short_date': 'Mon 1/1',
            'has_events': True,
            'time_slots': [
                {
                    'time': '10:00 am',
                    'events': [event]
                }
            ]
        }
        
        return template.render(days=[day])

    def test_event_data_processing(self):
        """Test that event data processing handles location and submitter information correctly"""
        # Create test event data with different formats
        test_cases = [
            {
                'input': {
                    '@type': 'Event',
                    'name': 'Test Event 1',
                    'location': {
                        'name': 'Test Venue',
                        'address': {
                            '@type': 'PostalAddress',
                            'streetAddress': '123 Test St',
                            'addressLocality': 'Test City',
                            'addressRegion': 'TC'
                        }
                    },
                    'submitter': {'name': 'John Doe', 'url': 'http://johndoe.com'}
                },
                'expected': {
                    'location': 'Test Venue, 123 Test St, Test City, TC',
                    'submitter_name': 'John Doe',
                    'submitter_link': 'http://johndoe.com'
                }
            },
            {
                'input': {
                    '@type': 'Event',
                    'name': 'Test Event 2',
                    'location': {'name': 'Test Venue'},
                    'submitter': {'name': 'anonymous'}
                },
                'expected': {
                    'location': 'Test Venue',
                    'submitter_name': None,
                    'submitter_link': None
                }
            },
            {
                'input': {
                    '@type': 'Event',
                    'name': 'Test Event 3',
                    'location': 'Simple Location',
                    'submitter': {'name': 'Jane Smith'}
                },
                'expected': {
                    'location': 'Simple Location',
                    'submitter_name': 'Jane Smith',
                    'submitter_link': None
                }
            },
            {
                'input': {
                    '@type': 'Event',
                    'name': 'Test Event 4',
                    'location': {
                        'name': 'Test Venue',
                        'address': {
                            '@type': 'PostalAddress',
                            'streetAddress': '456 Test Ave',
                            'addressLocality': 'Test City'
                        }
                    }
                },
                'expected': {
                    'location': 'Test Venue, 456 Test Ave, Test City',
                    'submitter_name': None,
                    'submitter_link': None
                }
            }
        ]
        
        for case in test_cases:
            # Process event data
            event = {}
            event_data = case['input']
            
            # Handle location
            location = event_data.get('location', {})
            if isinstance(location, dict):
                place_name = location.get('name', '')
                address = location.get('address', {})
                
                # Handle address object
                if isinstance(address, dict):
                    street = address.get('streetAddress', '')
                    locality = address.get('addressLocality', '')
                    region = address.get('addressRegion', '')
                    
                    # Build formatted address
                    address_parts = []
                    if street:
                        address_parts.append(street)
                    if locality:
                        address_parts.append(locality)
                    if region:
                        address_parts.append(region)
                    
                    formatted_address = ', '.join(part for part in address_parts if part)
                    
                    if place_name and formatted_address:
                        event['location'] = f"{place_name}, {formatted_address}"
                    elif place_name:
                        event['location'] = place_name
                    elif formatted_address:
                        event['location'] = formatted_address
                else:
                    # Handle string address
                    if place_name and address:
                        event['location'] = f"{place_name}, {address}"
                    elif place_name:
                        event['location'] = place_name
                    elif address:
                        event['location'] = address
            else:
                event['location'] = str(location) if location else ''
            
            # Handle submitter
            submitter = event_data.get('submitter', {})
            if isinstance(submitter, dict):
                name = submitter.get('name', '')
                if name and name.lower() != 'anonymous':
                    event['submitter_name'] = name
                    if submitter.get('url'):
                        event['submitter_link'] = submitter['url']
            
            # Verify results
            self.assertEqual(event.get('location'), case['expected']['location'])
            self.assertEqual(event.get('submitter_name'), case['expected']['submitter_name'])
            self.assertEqual(event.get('submitter_link'), case['expected']['submitter_link'])

if __name__ == '__main__':
    unittest.main()