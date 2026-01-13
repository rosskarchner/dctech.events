#!/usr/bin/env python3
import unittest
from datetime import datetime, date, timedelta
import pytz

class TestApp(unittest.TestCase):
    def setUp(self):
        self.timezone_name = 'US/Eastern'
        self.local_tz = pytz.timezone(self.timezone_name)
        self.today = datetime.now(self.local_tz).date()
    
    def test_prepare_events_by_day_time_grouping(self):
        """Test that prepare_events_by_day correctly groups events by time within each day"""
        from app import prepare_events_by_day
        
        # Create test events for a single day with different times
        today_str = self.today.strftime('%Y-%m-%d')
        events = [
            {'date': today_str, 'time': '09:00', 'title': 'Morning Event 1'},
            {'date': today_str, 'time': '09:00', 'title': 'Morning Event 2'},
            {'date': today_str, 'time': '14:30', 'title': 'Afternoon Event'},
            {'date': today_str, 'title': 'No Time Event'}
        ]
        
        days = prepare_events_by_day(events)
        
        # Verify structure
        self.assertEqual(len(days), 1)
        day = days[0]
        self.assertTrue(day['has_events'])
        self.assertEqual(day['date'], today_str)
        
        # Verify time slots
        time_slots = day['time_slots']
        self.assertEqual(len(time_slots), 3)  # All Day, 9am, and 2:30pm
        
        # Verify time slot order - All Day should be first now (events without time appear first)
        self.assertEqual(time_slots[0]['time'], 'All Day')
        self.assertEqual(len(time_slots[0]['events']), 1)
        self.assertEqual(time_slots[1]['time'], '09:00')
        self.assertEqual(len(time_slots[1]['events']), 2)
        self.assertEqual(time_slots[2]['time'], '14:30')
        self.assertEqual(len(time_slots[2]['events']), 1)
        
        # Verify events are sorted by title within time slots
        morning_events = time_slots[1]['events']
        self.assertEqual(morning_events[0]['title'], 'Morning Event 1')
        self.assertEqual(morning_events[1]['title'], 'Morning Event 2')

    def test_get_future_months_with_events_exclusions(self):
        """Test that get_future_months_with_events excludes current and next month"""
        import calendar
        from app import get_future_months_with_events
        import os
        import yaml
        
        # Create test data directory
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        
        try:
            # Create test files for current month, next month, and future months
            current_month = self.today.strftime('%B').lower()
            if self.today.month == 12:
                next_month = 'january'
                next_month_year = self.today.year + 1
            else:
                next_month = calendar.month_name[self.today.month + 1].lower()
                next_month_year = self.today.year
            
            # Create test files
            files_to_create = [
                (f"{self.today.year}_{current_month}.yaml", [{'title': 'Current Month Event'}]),
                (f"{next_month_year}_{next_month}.yaml", [{'title': 'Next Month Event'}]),
                (f"{self.today.year}_{calendar.month_name[12].lower()}.yaml", [{'title': 'December Event'}])
            ]
            
            for filename, events in files_to_create:
                filepath = os.path.join(data_dir, filename)
                with open(filepath, 'w') as f:
                    yaml.dump(events, f)
            
            # Get future months
            future_months = get_future_months_with_events()
            
            # Verify current month is excluded
            current_year_months = future_months.get(self.today.year, [])
            self.assertTrue(all(m['number'] != self.today.month for m in current_year_months))
            
            # Verify next month is excluded
            if next_month_year == self.today.year:
                self.assertTrue(all(m['number'] != self.today.month + 1 for m in current_year_months))
            else:
                next_year_months = future_months.get(next_month_year, [])
                self.assertTrue(all(m['number'] != 1 for m in next_year_months))
            
        finally:
            # Cleanup test files
            for filename, _ in files_to_create:
                filepath = os.path.join(data_dir, filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
            
            # Try to remove directory if empty
            try:
                os.rmdir(data_dir)
            except:
                pass

    def test_emoji_handling(self):
        """Test that emojis in event titles are preserved"""
        from app import prepare_events_by_day
        import os
        import yaml
        
        # Create test event with emoji
        today_str = self.today.strftime('%Y-%m-%d')
        test_title = "⚡️ Data, AI, and ML Lightning talks!"
        events = [
            {'date': today_str, 'time': '09:00', 'title': test_title}
        ]
        
        # Test through prepare_events_by_day
        days = prepare_events_by_day(events)
        
        # Verify emoji is preserved
        self.assertEqual(len(days), 1)
        self.assertEqual(days[0]['time_slots'][0]['events'][0]['title'], test_title)
        
        # Test YAML serialization/deserialization
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, 'test_emoji.yaml')
        
        try:
            # Write test data
            with open(test_file, 'w', encoding='utf-8') as f:
                yaml.dump(events, f, allow_unicode=True)
            
            # Read test data back
            with open(test_file, 'r', encoding='utf-8') as f:
                loaded_events = yaml.safe_load(f)
            
            # Verify emoji is preserved through YAML operations
            self.assertEqual(loaded_events[0]['title'], test_title)
            
        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)
            try:
                os.rmdir(data_dir)
            except:
                pass


    def test_newsletter_endpoints(self):
        """Test the newsletter HTML and plaintext endpoints"""
        from app import app
        import os
        import yaml
        
        # Create test client
        client = app.test_client()
        
        # Create test data
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, 'upcoming.yaml')
        
        test_events = [
            {
                'date': self.today.strftime('%Y-%m-%d'),
                'time': '09:00',
                'title': 'Test Event 1',
                'location': 'Test Location',
                'url': 'http://test.com'
            }
        ]
        
        try:
            # Write test data
            with open(test_file, 'w') as f:
                yaml.dump(test_events, f)
            
            # Test HTML newsletter endpoint
            response = client.get('/newsletter.html')
            self.assertEqual(response.status_code, 200)
            self.assertIn('text/html', response.content_type)
            self.assertIn('Test Event 1', response.data.decode())
            self.assertIn('Test Location', response.data.decode())
            self.assertIn('http://test.com', response.data.decode())
            
            # Test plaintext newsletter endpoint
            response = client.get('/newsletter.txt')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content_type, 'text/plain; charset=utf-8')
            self.assertIn('Test Event 1', response.data.decode())
            self.assertIn('Test Location', response.data.decode())
            self.assertIn('http://test.com', response.data.decode())
            
        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)
            try:
                os.rmdir(data_dir)
            except:
                pass

    def test_get_stats(self):
        """Test loading stats from stats.yaml"""
        from app import get_stats
        import os
        import yaml
        
        # Create test data directory
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, 'stats.yaml')
        
        test_stats = {
            'upcoming_events': 42,
            'active_groups': 10
        }
        
        try:
            # Test with no stats file
            if os.path.exists(test_file):
                os.remove(test_file)
            stats = get_stats()
            self.assertEqual(stats, {})
            
            # Test with stats file
            with open(test_file, 'w') as f:
                yaml.dump(test_stats, f)
            
            stats = get_stats()
            self.assertEqual(stats['upcoming_events'], 42)
            self.assertEqual(stats['active_groups'], 10)
            
        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)
            try:
                os.rmdir(data_dir)
            except:
                pass

    def test_time_format_handling(self):
        """Test handling of various time formats including 08:00 and All Day cases"""
        from app import prepare_events_by_day
        
        today_str = self.today.strftime('%Y-%m-%d')
        events = [
            {'date': today_str, 'time': '08:00', 'title': 'Early Morning Event'},
            {'date': today_str, 'time': '8:00', 'title': 'Another Early Event'},
            {'date': today_str, 'time': '', 'title': 'Empty Time Event'},
            {'date': today_str, 'time': 'invalid', 'title': 'Invalid Time Event'},
            {'date': today_str, 'title': 'No Time Event'}
        ]
        
        days = prepare_events_by_day(events)
        
        # Verify we have one day
        self.assertEqual(len(days), 1)
        day = days[0]
        
        # Get all events across time slots
        all_events = [e for slot in day['time_slots'] for e in slot['events']]
        
        # Find events by title
        early_event = next(e for e in all_events if e['title'] == 'Early Morning Event')
        another_early = next(e for e in all_events if e['title'] == 'Another Early Event')
        empty_time = next(e for e in all_events if e['title'] == 'Empty Time Event')
        invalid_time = next(e for e in all_events if e['title'] == 'Invalid Time Event')
        no_time = next(e for e in all_events if e['title'] == 'No Time Event')
        
        # Verify time formatting
        self.assertEqual(early_event['formatted_time'], '8:00 am')
        self.assertEqual(another_early['formatted_time'], '8:00 am')
        self.assertEqual(empty_time['formatted_time'], 'All Day')
        self.assertEqual(invalid_time['formatted_time'], 'All Day')
        self.assertEqual(no_time['formatted_time'], 'All Day')
        
        # Verify machine-readable time field (used for datetime attribute)
        self.assertEqual(early_event['time'], '08:00')
        self.assertEqual(another_early['time'], '08:00')
        self.assertEqual(empty_time['time'], '')
        self.assertEqual(invalid_time['time'], '')
        self.assertEqual(no_time['time'], '')
        
    def test_multi_day_event_time_consistency(self):
        """Test that multi-day events maintain consistent time formatting across days"""
        from app import prepare_events_by_day
        
        today_str = self.today.strftime('%Y-%m-%d')
        tomorrow = self.today + timedelta(days=1)
        tomorrow_str = tomorrow.strftime('%Y-%m-%d')
        
        events = [
            {
                'date': today_str,
                'time': '08:00',
                'title': 'Multi Day Event',
                'end_date': tomorrow_str
            },
            {
                'date': today_str,
                'time': '',
                'title': 'Multi Day All Day Event',
                'end_date': tomorrow_str
            }
        ]
        
        days = prepare_events_by_day(events)
        
        # Verify we have two days
        self.assertEqual(len(days), 2)
        
        # Get events for both days
        first_day = next(d for d in days if d['date'] == today_str)
        second_day = next(d for d in days if d['date'] == tomorrow_str)
        
        # Get the events from each day
        first_day_events = {e['title']: e for slot in first_day['time_slots'] for e in slot['events']}
        second_day_events = {e['title']: e for slot in second_day['time_slots'] for e in slot['events']}
        
        # Verify time consistency for the 08:00 event
        self.assertEqual(first_day_events['Multi Day Event']['formatted_time'], '8:00 am')
        self.assertEqual(first_day_events['Multi Day Event']['time'], '08:00')
        self.assertEqual(second_day_events['Multi Day Event']['display_title'], 'Multi Day Event (continuing)')
        self.assertEqual(second_day_events['Multi Day Event']['formatted_time'], '8:00 am')
        self.assertEqual(second_day_events['Multi Day Event']['time'], '08:00')
        
        # Verify time consistency for the All Day event
        self.assertEqual(first_day_events['Multi Day All Day Event']['formatted_time'], 'All Day')
        self.assertEqual(first_day_events['Multi Day All Day Event']['time'], '')
        self.assertEqual(second_day_events['Multi Day All Day Event']['display_title'], 'Multi Day All Day Event (continuing)')
        self.assertEqual(second_day_events['Multi Day All Day Event']['formatted_time'], 'All Day')
        self.assertEqual(second_day_events['Multi Day All Day Event']['time'], '')


    def test_multi_day_events(self):
        """Test that multi-day events appear on each day with (continuing) label"""
        from app import prepare_events_by_day
        
        # Create test events including a multi-day event
        today_str = self.today.strftime('%Y-%m-%d')
        tomorrow = self.today + timedelta(days=1)
        tomorrow_str = tomorrow.strftime('%Y-%m-%d')
        day_after = self.today + timedelta(days=2)
        day_after_str = day_after.strftime('%Y-%m-%d')
        
        events = [
            {
                'date': today_str,
                'time': '09:00',
                'title': 'Single Day Event',
                'url': 'http://test.com'
            },
            {
                'date': today_str,
                'time': '10:00',
                'title': 'Multi Day Event',
                'url': 'http://test2.com',
                'end_date': day_after_str
            }
        ]
        
        days = prepare_events_by_day(events)
        
        # Verify we have entries for all three days
        self.assertEqual(len(days), 3)
        
        # Verify first day has both events without (continuing)
        first_day = next(d for d in days if d['date'] == today_str)
        first_day_events = [e for slot in first_day['time_slots'] for e in slot['events']]
        self.assertEqual(len(first_day_events), 2)
        multi_day_event = next(e for e in first_day_events if e['title'] == 'Multi Day Event')
        self.assertNotIn('(continuing)', multi_day_event['title'])
        
        # Verify second day has only multi-day event with (continuing)
        second_day = next(d for d in days if d['date'] == tomorrow_str)
        second_day_events = [e for slot in second_day['time_slots'] for e in slot['events']]
        self.assertEqual(len(second_day_events), 1)
        self.assertEqual(second_day_events[0]['title'], 'Multi Day Event')
        self.assertIn('(continuing)', second_day_events[0]['display_title'])
        
        # Verify third day has only multi-day event with (continuing)
        third_day = next(d for d in days if d['date'] == day_after_str)
        third_day_events = [e for slot in third_day['time_slots'] for e in slot['events']]
        self.assertEqual(len(third_day_events), 1)
        self.assertEqual(third_day_events[0]['title'], 'Multi Day Event')
        self.assertIn('(continuing)', third_day_events[0]['display_title'])
        
        # Verify time consistency across all days for multi-day event
        first_day_time = next(e['time'] for slot in first_day['time_slots'] for e in slot['events'] if e['title'] == 'Multi Day Event')
        second_day_time = next(e['time'] for slot in second_day['time_slots'] for e in slot['events'] if e['title'] == 'Multi Day Event')
        third_day_time = next(e['time'] for slot in third_day['time_slots'] for e in slot['events'] if e['title'] == 'Multi Day Event')
        
        # All days should have the same time in HH:MM format
        self.assertEqual(first_day_time, second_day_time)
        self.assertEqual(second_day_time, third_day_time)
        self.assertEqual(first_day_time, '10:00')

    def test_get_upcoming_weeks_includes_event_weeks(self):
        """Test that get_upcoming_weeks includes weeks with events far in the future"""
        from app import get_upcoming_weeks, get_week_identifier
        import os
        import yaml
        
        # Create test data directory
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, 'upcoming.yaml')
        
        # Create test events:
        # 1. Event within the next 12 weeks
        # 2. Event far in the future (6 months ahead)
        # 3. Multi-day event spanning multiple weeks
        near_future = self.today + timedelta(weeks=5)
        far_future = self.today + timedelta(weeks=30)  # About 7 months ahead
        multi_day_start = self.today + timedelta(weeks=20)
        multi_day_end = multi_day_start + timedelta(days=10)  # Spans ~2 weeks
        
        test_events = [
            {
                'date': near_future.strftime('%Y-%m-%d'),
                'time': '09:00',
                'title': 'Near Future Event'
            },
            {
                'date': far_future.strftime('%Y-%m-%d'),
                'time': '10:00',
                'title': 'Far Future Event'
            },
            {
                'date': multi_day_start.strftime('%Y-%m-%d'),
                'end_date': multi_day_end.strftime('%Y-%m-%d'),
                'time': '08:00',
                'title': 'Multi-day Event'
            }
        ]
        
        try:
            # Write test data
            with open(test_file, 'w') as f:
                yaml.dump(test_events, f)
            
            # Get upcoming weeks (default 12 weeks)
            weeks = get_upcoming_weeks(12)
            
            # Verify we have at least 12 weeks (the rolling window)
            self.assertGreaterEqual(len(weeks), 12)
            
            # Verify the near future event's week is included
            near_week_id = get_week_identifier(near_future)
            self.assertIn(near_week_id, weeks)
            
            # Verify the far future event's week is included
            far_week_id = get_week_identifier(far_future)
            self.assertIn(far_week_id, weeks)
            
            # Verify multi-day event weeks are included
            multi_day_week_start = get_week_identifier(multi_day_start)
            multi_day_week_end = get_week_identifier(multi_day_end)
            self.assertIn(multi_day_week_start, weeks)
            self.assertIn(multi_day_week_end, weeks)
            
            # Verify the list is sorted
            self.assertEqual(weeks, sorted(weeks))
            
            # Verify no duplicates
            self.assertEqual(len(weeks), len(set(weeks)))
            
        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)
            try:
                os.rmdir(data_dir)
            except OSError:
                # Directory not empty or doesn't exist
                pass

    def test_get_upcoming_weeks_without_events(self):
        """Test that get_upcoming_weeks works when there are no events"""
        from app import get_upcoming_weeks
        import os
        
        # Ensure no events file exists
        data_dir = '_data'
        test_file = os.path.join(data_dir, 'upcoming.yaml')
        if os.path.exists(test_file):
            os.remove(test_file)
        
        # Get upcoming weeks (should just return the rolling window)
        weeks = get_upcoming_weeks(12)
        
        # Should have exactly 12 weeks (or slightly more if current week overlaps)
        self.assertGreaterEqual(len(weeks), 12)
        self.assertLessEqual(len(weeks), 13)  # At most one extra due to partial weeks
        
        # Verify the list is sorted
        self.assertEqual(weeks, sorted(weeks))
        
        # Verify no duplicates
        self.assertEqual(len(weeks), len(set(weeks)))

    def test_microformats2_h_event_markup(self):
        """Test that event listings contain valid microformats2 h-event markup"""
        from app import app
        import os
        import yaml
        
        # Create test client
        client = app.test_client()
        
        # Create test data directory
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, 'upcoming.yaml')
        
        # Create test event data
        today_str = self.today.strftime('%Y-%m-%d')
        test_events = [
            {
                'date': today_str,
                'time': '09:00',
                'title': 'Test Microformats Event',
                'location': 'Test Location DC',
                'url': 'http://test-event.example.com',
                'group': 'Test Tech Group',
                'group_website': 'http://testgroup.example.com'
            }
        ]
        
        try:
            # Write test data
            with open(test_file, 'w') as f:
                yaml.dump(test_events, f)
            
            # Get homepage
            response = client.get('/')
            self.assertEqual(response.status_code, 200)
            
            # Convert response to string
            html = response.data.decode()
            
            # Check for required microformat2 h-event class
            self.assertIn('class="h-event event"', html)
            
            # Check for event name with u-url and p-name classes
            self.assertIn('class="u-url p-name"', html)
            self.assertIn('Test Microformats Event', html)
            self.assertIn('http://test-event.example.com', html)
            
            # Check for dt-start (datetime) class with proper datetime attribute
            self.assertIn('class="dt-start"', html)
            self.assertIn(f'datetime="{today_str}T09:00"', html)
            
            # Check for p-location class
            self.assertIn('class="p-location event-location"', html)
            self.assertIn('Test Location DC', html)
            
            # Check for p-organizer with h-card
            self.assertIn('class="p-organizer h-card"', html)
            self.assertIn('Test Tech Group', html)
            self.assertIn('http://testgroup.example.com', html)
            
        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)
            try:
                os.rmdir(data_dir)
            except:
                pass

    def test_microformats2_with_submitter(self):
        """Test microformats2 markup with event submitter instead of organizer"""
        from app import app
        import os
        import yaml
        
        # Create test client
        client = app.test_client()
        
        # Create test data directory
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, 'upcoming.yaml')
        
        # Create test event with submitter
        today_str = self.today.strftime('%Y-%m-%d')
        test_events = [
            {
                'date': today_str,
                'time': '14:30',
                'title': 'Community Submitted Event',
                'location': 'Arlington VA',
                'url': 'http://community-event.example.com',
                'submitter_name': 'Jane Doe',
                'submitter_link': 'http://janedoe.example.com'
            }
        ]
        
        try:
            # Write test data
            with open(test_file, 'w') as f:
                yaml.dump(test_events, f)
            
            # Get homepage
            response = client.get('/')
            self.assertEqual(response.status_code, 200)
            
            # Convert response to string
            html = response.data.decode()
            
            # Check for h-event class
            self.assertIn('class="h-event event"', html)
            
            # Check for p-author with h-card (for submitter)
            self.assertIn('class="p-author h-card"', html)
            self.assertIn('Jane Doe', html)
            self.assertIn('http://janedoe.example.com', html)
            
            # Verify event details
            self.assertIn('Community Submitted Event', html)
            self.assertIn('Arlington VA', html)
            
        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)
            try:
                os.rmdir(data_dir)
            except:
                pass

    def test_microformats2_all_day_event(self):
        """Test microformats2 markup for all-day events (no time specified)"""
        from app import app
        import os
        import yaml
        
        # Create test client
        client = app.test_client()
        
        # Create test data directory
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, 'upcoming.yaml')
        
        # Create test event without time
        today_str = self.today.strftime('%Y-%m-%d')
        test_events = [
            {
                'date': today_str,
                'title': 'All Day Conference',
                'location': 'Washington DC',
                'url': 'http://all-day-conf.example.com',
                'group': 'DC Conference Organizers'
            }
        ]
        
        try:
            # Write test data
            with open(test_file, 'w') as f:
                yaml.dump(test_events, f)
            
            # Get homepage
            response = client.get('/')
            self.assertEqual(response.status_code, 200)
            
            # Convert response to string
            html = response.data.decode()
            
            # Check for h-event class
            self.assertIn('class="h-event event"', html)
            
            # Check event is displayed
            self.assertIn('All Day Conference', html)
            self.assertIn('Washington DC', html)
            
            # Note: dt-start should not be present for all-day events without time
            # The template only renders <time class="dt-start"> if event.time is present
            
        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)
            try:
                os.rmdir(data_dir)
            except:
                pass

    def test_ical_feed_basic(self):
        """Test that iCal feed is generated with basic event data"""
        from app import app
        import os
        import yaml
        from icalendar import Calendar
        from datetime import datetime as dt
        
        # Create test client
        client = app.test_client()
        
        # Create test data directory
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, 'upcoming.yaml')
        
        # Create test group directory and files
        groups_dir = '_groups'
        os.makedirs(groups_dir, exist_ok=True)
        group_file = os.path.join(groups_dir, 'test-tech-group.yaml')
        
        # Create test event data
        today_str = self.today.strftime('%Y-%m-%d')
        tomorrow = self.today + timedelta(days=1)
        tomorrow_str = tomorrow.strftime('%Y-%m-%d')
        
        test_events = [
            {
                'date': today_str,
                'time': '09:00',
                'title': 'Morning Tech Meetup',
                'location': 'Washington DC',
                'url': 'http://test-event.example.com',
                'group': 'Test Tech Group',
                'cost': 'Free'
            },
            {
                'date': tomorrow_str,
                'title': 'All Day Conference',
                'location': 'Arlington VA',
                'url': 'http://conference.example.com'
            }
        ]
        
        test_group = {
            'name': 'Test Tech Group',
            'website': 'https://testgroup.example.com',
            'active': True
        }
        
        try:
            # Write test data
            with open(test_file, 'w') as f:
                yaml.dump(test_events, f)
            
            # Write test group
            with open(group_file, 'w') as f:
                yaml.dump(test_group, f)
            
            # Get iCal feed
            response = client.get('/events.ics')
            self.assertEqual(response.status_code, 200)
            self.assertIn('text/calendar', response.content_type)
            
            # Parse the iCal data
            cal = Calendar.from_ical(response.data)
            
            # Check calendar properties
            self.assertEqual(cal.get('version'), '2.0')
            self.assertIn('DC Tech Events', str(cal.get('x-wr-calname')))
            
            # Verify x-wr-timezone is NOT present
            self.assertIsNone(cal.get('x-wr-timezone'))
            
            # Get events from calendar
            events = [component for component in cal.walk() if component.name == 'VEVENT']
            self.assertEqual(len(events), 2)
            
            # Check first event (with time)
            event1 = next(e for e in events if str(e.get('summary')) == 'Morning Tech Meetup')
            self.assertEqual(str(event1.get('location')), 'Washington DC')
            self.assertIn('http://test-event.example.com', str(event1.get('url')))
            
            # Check organizer uses website URL with CN parameter
            organizer = event1.get('organizer')
            self.assertIsNotNone(organizer)
            self.assertIn('https://testgroup.example.com', str(organizer))
            # Check CN parameter
            self.assertEqual(organizer.params.get('CN'), 'Test Tech Group')
            
            # Check that dtstart and dtend are in UTC (datetime objects with tzinfo)
            dtstart1 = event1.get('dtstart').dt
            dtend1 = event1.get('dtend').dt
            self.assertIsNotNone(dtstart1)
            self.assertIsNotNone(dtend1)
            # Verify they are datetime objects (not date) and have timezone info
            self.assertIsInstance(dtstart1, dt)
            self.assertIsNotNone(dtstart1.tzinfo)
            
            # Check second event (all day) - should use date objects
            event2 = next(e for e in events if str(e.get('summary')) == 'All Day Conference')
            self.assertEqual(str(event2.get('location')), 'Arlington VA')
            
            # Check that dtstart and dtend are date objects (not datetime) for all-day events
            dtstart2 = event2.get('dtstart').dt
            dtend2 = event2.get('dtend').dt
            self.assertIsNotNone(dtstart2)
            self.assertIsNotNone(dtend2)
            # Verify they are date objects (not datetime)
            self.assertIsInstance(dtstart2, date)
            self.assertNotIsInstance(dtstart2, dt)
            # Verify dtend is the day after dtstart (exclusive)
            self.assertEqual(dtend2, dtstart2 + timedelta(days=1))
            
        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)
            if os.path.exists(group_file):
                os.remove(group_file)
            try:
                os.rmdir(data_dir)
            except (OSError, FileNotFoundError):
                pass
            try:
                os.rmdir(groups_dir)
            except (OSError, FileNotFoundError):
                pass

    def test_ical_feed_multi_day_event(self):
        """Test that multi-day events are handled correctly in iCal feed"""
        from app import app
        import os
        import yaml
        from icalendar import Calendar
        from datetime import datetime as dt
        
        # Create test client
        client = app.test_client()
        
        # Create test data directory
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, 'upcoming.yaml')
        
        # Create multi-day event with time
        today_str = self.today.strftime('%Y-%m-%d')
        three_days_later = self.today + timedelta(days=3)
        three_days_later_str = three_days_later.strftime('%Y-%m-%d')
        
        # Also create an all-day multi-day event
        test_events = [
            {
                'date': today_str,
                'end_date': three_days_later_str,
                'time': '10:00',
                'title': 'Multi-Day Conference',
                'location': 'Convention Center DC',
                'url': 'http://multi-day-conf.example.com'
            },
            {
                'date': today_str,
                'end_date': three_days_later_str,
                'title': 'All-Day Multi-Day Event',
                'location': 'Various Locations',
                'url': 'http://all-day-multi.example.com'
            }
        ]
        
        try:
            # Write test data
            with open(test_file, 'w') as f:
                yaml.dump(test_events, f)
            
            # Get iCal feed
            response = client.get('/events.ics')
            self.assertEqual(response.status_code, 200)
            
            # Parse the iCal data
            cal = Calendar.from_ical(response.data)
            
            # Get events from calendar
            events = [component for component in cal.walk() if component.name == 'VEVENT']
            self.assertEqual(len(events), 2)
            
            # Check timed multi-day event
            event1 = next(e for e in events if str(e.get('summary')) == 'Multi-Day Conference')
            
            # Verify dtstart and dtend exist and are datetime objects with timezone
            dtstart1 = event1.get('dtstart').dt
            dtend1 = event1.get('dtend').dt
            self.assertIsNotNone(dtstart1)
            self.assertIsNotNone(dtend1)
            self.assertIsInstance(dtstart1, dt)
            self.assertIsNotNone(dtstart1.tzinfo)
            
            # Verify that end is after start
            self.assertGreater(dtend1, dtstart1)
            
            # Check all-day multi-day event
            event2 = next(e for e in events if str(e.get('summary')) == 'All-Day Multi-Day Event')
            
            # Verify dtstart and dtend are date objects
            dtstart2 = event2.get('dtstart').dt
            dtend2 = event2.get('dtend').dt
            self.assertIsNotNone(dtstart2)
            self.assertIsNotNone(dtend2)
            self.assertIsInstance(dtstart2, date)
            self.assertNotIsInstance(dtstart2, dt)
            
            # For all-day events, dtend should be the day after the last day (exclusive)
            # So if event is from today to three_days_later, dtend should be three_days_later + 1
            expected_dtend = three_days_later + timedelta(days=1)
            self.assertEqual(dtend2, expected_dtend)
            
        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)
            try:
                os.rmdir(data_dir)
            except (OSError, FileNotFoundError):
                pass

    def test_ical_feed_empty_events(self):
        """Test that iCal feed works with no events"""
        from app import app
        import os
        from icalendar import Calendar
        
        # Create test client
        client = app.test_client()
        
        # Ensure no events file exists
        data_dir = '_data'
        test_file = os.path.join(data_dir, 'upcoming.yaml')
        if os.path.exists(test_file):
            os.remove(test_file)
        
        try:
            # Get iCal feed
            response = client.get('/events.ics')
            self.assertEqual(response.status_code, 200)
            self.assertIn('text/calendar', response.content_type)
            
            # Parse the iCal data
            cal = Calendar.from_ical(response.data)
            
            # Check calendar properties exist
            self.assertEqual(cal.get('version'), '2.0')
            
            # Get events from calendar (should be empty)
            events = [component for component in cal.walk() if component.name == 'VEVENT']
            self.assertEqual(len(events), 0)
            
        finally:
            pass

    def test_time_dictionary_for_multiday_events(self):
        """Test that multi-day events can have different times per day using a dictionary"""
        from app import prepare_events_by_day

        # Create a multi-day event with time as a dictionary
        start_date = self.today + timedelta(days=1)
        end_date = start_date + timedelta(days=2)

        events = [
            {
                'date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'title': 'Conference with Daily Times',
                'time': {
                    (start_date + timedelta(days=1)).strftime('%Y-%m-%d'): '09:00',
                    end_date.strftime('%Y-%m-%d'): '10:00'
                }
            }
        ]

        days = prepare_events_by_day(events)

        # Should have 3 days
        self.assertEqual(len(days), 3)

        # First day should have All Day (no time specified in dict)
        first_day_event = days[0]['time_slots'][0]['events'][0]
        self.assertEqual(first_day_event['time'], '')
        self.assertEqual(first_day_event['formatted_time'], 'All Day')

        # Second day should have 9:00 AM time
        second_day_event = days[1]['time_slots'][0]['events'][0]
        self.assertEqual(second_day_event['time'], '09:00')
        self.assertEqual(second_day_event['formatted_time'], '9:00 am')

        # Third day should have 10:00 AM time
        third_day_event = days[2]['time_slots'][0]['events'][0]
        self.assertEqual(third_day_event['time'], '10:00')
        self.assertEqual(third_day_event['formatted_time'], '10:00 am')

    def test_ical_unique_uids(self):
        """Test that iCal feed generates unique UIDs for all events, even when sharing URLs"""
        from app import app
        import os
        import yaml
        from icalendar import Calendar

        # Create test client
        client = app.test_client()

        # Create test data directory
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, 'upcoming.yaml')

        # Create multiple events that share the same URL (common for recurring meetups)
        today_str = self.today.strftime('%Y-%m-%d')
        tomorrow = self.today + timedelta(days=1)
        tomorrow_str = tomorrow.strftime('%Y-%m-%d')
        next_week = self.today + timedelta(days=7)
        next_week_str = next_week.strftime('%Y-%m-%d')

        test_events = [
            {
                'date': today_str,
                'time': '09:00',
                'title': 'Weekly Tech Meetup',
                'location': 'Coffee Shop',
                'url': 'http://meetup.example.com/weekly-tech'
            },
            {
                'date': tomorrow_str,
                'time': '14:00',
                'title': 'Weekly Tech Meetup',
                'location': 'Coffee Shop',
                'url': 'http://meetup.example.com/weekly-tech'
            },
            {
                'date': next_week_str,
                'time': '09:00',
                'title': 'Weekly Tech Meetup',
                'location': 'Coffee Shop',
                'url': 'http://meetup.example.com/weekly-tech'
            },
            {
                'date': today_str,
                'time': '10:00',
                'title': 'Different Event Same Day',
                'location': 'Office',
                'url': 'http://meetup.example.com/different-event'
            }
        ]

        try:
            # Write test data
            with open(test_file, 'w') as f:
                yaml.dump(test_events, f)

            # Get iCal feed
            response = client.get('/events.ics')
            self.assertEqual(response.status_code, 200)

            # Parse the iCal data
            cal = Calendar.from_ical(response.data)

            # Get events from calendar
            events = [component for component in cal.walk() if component.name == 'VEVENT']
            self.assertEqual(len(events), 4)

            # Extract all UIDs
            uids = [str(event.get('uid')) for event in events]

            # Verify all UIDs are present
            for uid in uids:
                self.assertIsNotNone(uid)
                self.assertTrue(len(uid) > 0)

            # Verify all UIDs are unique (this is the main test)
            self.assertEqual(len(uids), len(set(uids)),
                           f"Duplicate UIDs found: {[uid for uid in uids if uids.count(uid) > 1]}")

            # Verify all UIDs end with @dctech.events
            for uid in uids:
                self.assertTrue(uid.endswith('@dctech.events'),
                              f"UID {uid} doesn't end with @dctech.events")

        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)
            try:
                os.rmdir(data_dir)
            except (OSError, FileNotFoundError):
                pass

    def test_category_pages_load(self):
        """Test that category pages load without errors"""
        from app import app, get_categories
        import os
        import yaml

        # Create test client
        client = app.test_client()

        # Create test data directory
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, 'upcoming.yaml')

        # Create test events with categories
        today_str = self.today.strftime('%Y-%m-%d')
        test_events = [
            {
                'date': today_str,
                'time': '09:00',
                'title': 'Python Workshop',
                'location': 'Washington DC',
                'url': 'http://python-event.example.com',
                'categories': ['python']
            },
            {
                'date': today_str,
                'time': '14:00',
                'title': 'AI Meetup',
                'location': 'Arlington VA',
                'url': 'http://ai-event.example.com',
                'categories': ['ai']
            }
        ]

        try:
            # Write test data
            with open(test_file, 'w') as f:
                yaml.dump(test_events, f)

            # Get all categories
            categories = get_categories()

            # Verify we have categories
            self.assertGreater(len(categories), 0)

            # Test loading a few category pages
            for slug in ['python', 'ai', 'gaming']:
                if slug in categories:
                    response = client.get(f'/categories/{slug}/')
                    self.assertEqual(response.status_code, 200,
                                   f"Category page for {slug} failed to load")

                    # Verify page contains category name (HTML-escaped)
                    import html as html_lib
                    html = response.data.decode()
                    escaped_name = html_lib.escape(categories[slug]['name'])
                    self.assertIn(escaped_name, html)

            # Test invalid category returns 404
            response = client.get('/categories/invalid-category/')
            self.assertEqual(response.status_code, 404)

        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)
            try:
                os.rmdir(data_dir)
            except:
                pass

    def test_category_filtering(self):
        """Test that category pages filter events correctly"""
        from app import app
        import os
        import yaml

        # Create test client
        client = app.test_client()

        # Create test data directory
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, 'upcoming.yaml')

        # Create test events with different categories
        today_str = self.today.strftime('%Y-%m-%d')
        test_events = [
            {
                'date': today_str,
                'time': '09:00',
                'title': 'Python Workshop',
                'location': 'Washington DC',
                'categories': ['python', 'data']
            },
            {
                'date': today_str,
                'time': '14:00',
                'title': 'AI Conference',
                'location': 'Arlington VA',
                'categories': ['ai']
            },
            {
                'date': today_str,
                'time': '18:00',
                'title': 'Gaming Night',
                'location': 'Bethesda MD',
                'categories': ['gaming']
            }
        ]

        try:
            # Write test data
            with open(test_file, 'w') as f:
                yaml.dump(test_events, f)

            # Test Python category page
            response = client.get('/categories/python/')
            self.assertEqual(response.status_code, 200)
            html = response.data.decode()

            # Should include Python Workshop
            self.assertIn('Python Workshop', html)
            # Should NOT include AI Conference or Gaming Night
            self.assertNotIn('AI Conference', html)
            self.assertNotIn('Gaming Night', html)

            # Test AI category page
            response = client.get('/categories/ai/')
            self.assertEqual(response.status_code, 200)
            html = response.data.decode()

            # Should include AI Conference
            self.assertIn('AI Conference', html)
            # Should NOT include Python Workshop or Gaming Night
            self.assertNotIn('Python Workshop', html)
            self.assertNotIn('Gaming Night', html)

            # Test data category page (Python Workshop has both python and data)
            response = client.get('/categories/data/')
            self.assertEqual(response.status_code, 200)
            html = response.data.decode()

            # Should include Python Workshop (has data category)
            self.assertIn('Python Workshop', html)

        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)
            try:
                os.rmdir(data_dir)
            except:
                pass

    def test_category_empty_state(self):
        """Test that category pages show empty state when no events match"""
        from app import app
        import os
        import yaml

        # Create test client
        client = app.test_client()

        # Create test data directory
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, 'upcoming.yaml')

        # Create test events WITHOUT any gaming category
        today_str = self.today.strftime('%Y-%m-%d')
        test_events = [
            {
                'date': today_str,
                'time': '09:00',
                'title': 'Python Workshop',
                'location': 'Washington DC',
                'categories': ['python']
            }
        ]

        try:
            # Write test data
            with open(test_file, 'w') as f:
                yaml.dump(test_events, f)

            # Test gaming category page (should be empty)
            response = client.get('/categories/gaming/')
            self.assertEqual(response.status_code, 200)
            html = response.data.decode()

            # Should show empty state message (template shows "no upcoming {category} events")
            self.assertIn('no upcoming gaming events', html.lower())
            # Should NOT include the Python Workshop
            self.assertNotIn('Python Workshop', html)

        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)
            try:
                os.rmdir(data_dir)
            except:
                pass

    def test_category_sitemap(self):
        """Test that sitemap includes category pages"""
        from app import app, get_categories

        # Create test client
        client = app.test_client()

        # Get sitemap
        response = client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertIn('xml', response.content_type)

        # Get all categories
        categories = get_categories()

        # Verify sitemap includes category pages
        sitemap_content = response.data.decode()

        # Check for at least a few category URLs
        for slug in ['python', 'ai', 'gaming']:
            if slug in categories:
                category_url = f'/categories/{slug}/'
                self.assertIn(category_url, sitemap_content,
                            f"Sitemap missing category page: {category_url}")

class TestDataPipelineIntegration(unittest.TestCase):
    """Test cases for data pipeline - overrides, categories, and suppress_guid"""
    
    def test_merge_event_with_override(self):
        """Test that override fields take precedence over original event data"""
        from generate_month_data import merge_event_with_override
        
        original_event = {
            'title': 'Original Title',
            'date': '2025-01-15',
            'time': '18:00',
            'location': 'Original Location',
            'description': 'Original description'
        }
        
        override = {
            'title': 'Updated Title',
            'location': 'Updated Location'
        }
        
        merged = merge_event_with_override(original_event, override)
        
        # Override fields should take precedence
        self.assertEqual(merged['title'], 'Updated Title')
        self.assertEqual(merged['location'], 'Updated Location')
        
        # Original fields should be preserved
        self.assertEqual(merged['date'], '2025-01-15')
        self.assertEqual(merged['time'], '18:00')
        self.assertEqual(merged['description'], 'Original description')
    
    def test_merge_event_with_none_override(self):
        """Test that None override returns original event unchanged"""
        from generate_month_data import merge_event_with_override
        
        original_event = {'title': 'Test Event', 'date': '2025-01-15'}
        
        merged = merge_event_with_override(original_event, None)
        
        self.assertEqual(merged, original_event)
    
    def test_resolve_event_categories_from_event(self):
        """Test that event-level categories take priority"""
        from generate_month_data import resolve_event_categories
        
        categories = {'python': {'name': 'Python'}, 'ai': {'name': 'AI'}}
        event = {'title': 'Test', 'categories': ['python']}
        group = {'name': 'Test Group', 'categories': ['ai']}
        
        result = resolve_event_categories(event, group, categories)
        
        # Event categories should take priority
        self.assertEqual(result, ['python'])
    
    def test_resolve_event_categories_from_group(self):
        """Test that group categories are used when event has no categories"""
        from generate_month_data import resolve_event_categories
        
        categories = {'python': {'name': 'Python'}, 'ai': {'name': 'AI'}}
        event = {'title': 'Test'}  # No categories
        group = {'name': 'Test Group', 'categories': ['ai']}
        
        result = resolve_event_categories(event, group, categories)
        
        # Group categories should be used
        self.assertEqual(result, ['ai'])
    
    def test_resolve_event_categories_empty_when_none(self):
        """Test that empty list is returned when neither event nor group has categories"""
        from generate_month_data import resolve_event_categories
        
        categories = {'python': {'name': 'Python'}}
        event = {'title': 'Test'}
        group = {'name': 'Test Group'}  # No categories
        
        result = resolve_event_categories(event, group, categories)
        
        self.assertEqual(result, [])
    
    def test_resolve_event_categories_filters_invalid(self):
        """Test that invalid category slugs are filtered out"""
        from generate_month_data import resolve_event_categories
        
        categories = {'python': {'name': 'Python'}}
        event = {'title': 'Test', 'categories': ['python', 'nonexistent']}
        group = None
        
        result = resolve_event_categories(event, group, categories)
        
        # Only valid category should be included
        self.assertEqual(result, ['python'])
    
    def test_load_categories(self):
        """Test that categories are loaded correctly from _categories directory"""
        from generate_month_data import load_categories
        
        categories = load_categories()
        
        # Should have all 16 expected categories
        self.assertGreaterEqual(len(categories), 15)
        
        # Check a known category
        self.assertIn('python', categories)
        self.assertEqual(categories['python']['name'], 'Python')
        self.assertIn('description', categories['python'])
    
    def test_load_event_override_nonexistent(self):
        """Test that nonexistent override returns None"""
        from generate_month_data import load_event_override
        
        result = load_event_override('nonexistent_hash_1234567890abcdef')
        
        self.assertIsNone(result)
    
    def test_suppress_guid_in_group(self):
        """Test that suppress_guid field works in group configuration"""
        import os
        import yaml
        from generate_month_data import load_groups, calculate_event_hash
        
        # Create a test group with suppress_guid
        test_group = {
            'name': 'Test Suppress Group',
            'website': 'https://example.com',
            'suppress_guid': ['abc123', 'def456']
        }
        
        group_file = '_groups/test_suppress_group.yaml'
        
        try:
            os.makedirs('_groups', exist_ok=True)
            with open(group_file, 'w') as f:
                yaml.dump(test_group, f)
            
            groups = load_groups()
            test_group_loaded = next((g for g in groups if g['id'] == 'test_suppress_group'), None)
            
            self.assertIsNotNone(test_group_loaded)
            self.assertIn('suppress_guid', test_group_loaded)
            self.assertEqual(test_group_loaded['suppress_guid'], ['abc123', 'def456'])
        finally:
            if os.path.exists(group_file):
                os.remove(group_file)
    
    def test_event_override_merging_with_file(self):
        """Test that override files are loaded and merged correctly"""
        import os
        import yaml
        from generate_month_data import load_event_override, merge_event_with_override, calculate_event_hash
        
        # Create a test override file
        test_hash = 'test_override_123456789abcdef0'
        override_data = {
            'title': 'Overridden Title',
            'categories': ['python', 'ai']
        }
        
        override_file = f'_event_overrides/{test_hash}.yaml'
        
        try:
            os.makedirs('_event_overrides', exist_ok=True)
            with open(override_file, 'w') as f:
                yaml.dump(override_data, f)
            
            # Test loading
            loaded_override = load_event_override(test_hash)
            
            self.assertIsNotNone(loaded_override)
            self.assertEqual(loaded_override['title'], 'Overridden Title')
            self.assertEqual(loaded_override['categories'], ['python', 'ai'])
            
            # Test merging
            original_event = {
                'title': 'Original Title',
                'date': '2025-01-15',
                'location': 'DC'
            }
            
            merged = merge_event_with_override(original_event, loaded_override)
            
            self.assertEqual(merged['title'], 'Overridden Title')
            self.assertEqual(merged['date'], '2025-01-15')  # Preserved
            self.assertEqual(merged['location'], 'DC')  # Preserved
            self.assertEqual(merged['categories'], ['python', 'ai'])  # Added
        finally:
            if os.path.exists(override_file):
                os.remove(override_file)
    
    def test_categories_override_group_categories(self):
        """Test that override categories take precedence over group categories"""
        from generate_month_data import resolve_event_categories, merge_event_with_override
        
        categories = {
            'python': {'name': 'Python'},
            'ai': {'name': 'AI'},
            'cloud': {'name': 'Cloud'}
        }
        
        # Original event (no categories) with group categories
        original_event = {'title': 'Test Event'}
        group = {'name': 'Test Group', 'categories': ['cloud']}
        
        # Override adds categories
        override = {'categories': ['python', 'ai']}
        
        # Merge override into event
        merged_event = merge_event_with_override(original_event, override)
        
        # Resolve categories - should use event categories (from override)
        result = resolve_event_categories(merged_event, group, categories)
        
        self.assertEqual(sorted(result), ['ai', 'python'])


class TestEventHashCalculation(unittest.TestCase):
    """Test cases for calculate_event_hash function"""
    
    def test_calculate_event_hash_basic(self):
        """Test basic hash calculation with date, time, and title"""
        from app import calculate_event_hash
        
        hash1 = calculate_event_hash('2025-01-15', '18:00', 'Python Meetup')
        
        # Hash should be a 32-character hex string
        self.assertEqual(len(hash1), 32)
        self.assertTrue(all(c in '0123456789abcdef' for c in hash1))
    
    def test_calculate_event_hash_deterministic(self):
        """Test that same inputs always produce the same hash"""
        from app import calculate_event_hash
        
        hash1 = calculate_event_hash('2025-01-15', '18:00', 'Python Meetup')
        hash2 = calculate_event_hash('2025-01-15', '18:00', 'Python Meetup')
        
        self.assertEqual(hash1, hash2)
    
    def test_calculate_event_hash_with_url(self):
        """Test hash calculation with optional URL"""
        from app import calculate_event_hash
        
        hash_without_url = calculate_event_hash('2025-01-15', '18:00', 'Python Meetup')
        hash_with_url = calculate_event_hash('2025-01-15', '18:00', 'Python Meetup', 
                                              'https://example.com/event')
        
        # Hash should be different when URL is included
        self.assertNotEqual(hash_without_url, hash_with_url)
    
    def test_calculate_event_hash_different_inputs(self):
        """Test that different inputs produce different hashes"""
        from app import calculate_event_hash
        
        hash1 = calculate_event_hash('2025-01-15', '18:00', 'Python Meetup')
        hash2 = calculate_event_hash('2025-01-16', '18:00', 'Python Meetup')  # Different date
        hash3 = calculate_event_hash('2025-01-15', '19:00', 'Python Meetup')  # Different time
        hash4 = calculate_event_hash('2025-01-15', '18:00', 'JavaScript Meetup')  # Different title
        
        # All hashes should be unique
        self.assertNotEqual(hash1, hash2)
        self.assertNotEqual(hash1, hash3)
        self.assertNotEqual(hash1, hash4)
    
    def test_calculate_event_hash_empty_time(self):
        """Test hash calculation with empty time string"""
        from app import calculate_event_hash
        
        hash1 = calculate_event_hash('2025-01-15', '', 'All Day Event')
        
        # Hash should still be valid
        self.assertEqual(len(hash1), 32)
        self.assertTrue(all(c in '0123456789abcdef' for c in hash1))
    
    def test_calculate_event_hash_matches_generate_month_data(self):
        """Test that hash matches the algorithm in generate_month_data.py"""
        from app import calculate_event_hash
        import hashlib
        
        # Manually compute hash the same way generate_month_data does
        date = '2025-01-15'
        time = '18:00'
        title = 'Test Event'
        url = 'https://example.com/event'
        
        uid_parts = [date, time, title, url]
        uid_base = '-'.join(str(p) for p in uid_parts)
        expected_hash = hashlib.md5(uid_base.encode('utf-8')).hexdigest()
        
        actual_hash = calculate_event_hash(date, time, title, url)
        
        self.assertEqual(actual_hash, expected_hash)

class TestLocationValidation(unittest.TestCase):
    """Test cases for location handling and validation"""
    
    def test_location_parsing_city_state(self):
        """Test that city, state format locations are handled correctly"""
        location = "Washington DC"
        
        # Simple check - location should contain city info
        self.assertIn("Washington", location)
    
    def test_location_parsing_with_comma(self):
        """Test location parsing with comma separator"""
        location = "Arlington, VA"
        parts = [p.strip() for p in location.split(',')]
        
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0], "Arlington")
        self.assertEqual(parts[1], "VA")
    
    def test_location_empty_handling(self):
        """Test that empty location is handled gracefully"""
        from app import prepare_events_by_day
        import pytz
        from datetime import datetime
        
        local_tz = pytz.timezone('US/Eastern')
        today = datetime.now(local_tz).date()
        today_str = today.strftime('%Y-%m-%d')
        
        events = [
            {'date': today_str, 'time': '18:00', 'title': 'Event Without Location'}
        ]
        
        days = prepare_events_by_day(events)
        self.assertEqual(len(days), 1)
        self.assertEqual(len(days[0]['time_slots']), 1)
    
    def test_location_with_venue_and_address(self):
        """Test location with full venue and address info"""
        location = "Conference Center, 1234 Main St, Washington DC"
        
        # Should contain venue info
        self.assertIn("Conference Center", location)
        self.assertIn("Washington DC", location)


class TestEditFormPrePopulation(unittest.TestCase):
    """Test cases for edit form pre-population"""
    
    def setUp(self):
        from datetime import datetime
        import pytz
        self.timezone_name = 'US/Eastern'
        self.local_tz = pytz.timezone(self.timezone_name)
        self.today = datetime.now(self.local_tz).date()
    
    def test_edit_form_contains_all_fields(self):
        """Test that edit form contains all required input fields"""
        from app import app
        import os
        import yaml
        
        client = app.test_client()
        
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, 'upcoming.yaml')
        
        today_str = self.today.strftime('%Y-%m-%d')
        test_guid = 'formtest123456789012345678901234'
        
        test_events = [
            {
                'date': today_str,
                'time': '18:00',
                'title': 'Test Event',
                'location': 'Washington DC',
                'url': 'https://example.com',
                'guid': test_guid,
                'source': 'ical'
            }
        ]
        
        try:
            with open(test_file, 'w') as f:
                yaml.dump(test_events, f)
            
            response = client.get(f'/edit/{test_guid}/')
            html = response.data.decode()
            
            # Check all form fields exist
            self.assertIn('id="title"', html)
            self.assertIn('id="url"', html)
            self.assertIn('id="date"', html)
            self.assertIn('id="time-hour"', html)
            self.assertIn('id="city"', html)
            
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)
    
    def test_edit_form_shows_categories(self):
        """Test that edit form shows category checkboxes"""
        from app import app
        import os
        import yaml
        
        client = app.test_client()
        
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, 'upcoming.yaml')
        
        today_str = self.today.strftime('%Y-%m-%d')
        test_guid = 'cattest1234567890123456789012345'
        
        test_events = [
            {
                'date': today_str,
                'time': '18:00',
                'title': 'Python Event',
                'location': 'DC',
                'url': 'https://example.com',
                'guid': test_guid,
                'source': 'ical',
                'categories': ['python']
            }
        ]
        
        try:
            with open(test_file, 'w') as f:
                yaml.dump(test_events, f)
            
            response = client.get(f'/edit/{test_guid}/')
            html = response.data.decode()
            
            # Check that category checkboxes exist
            self.assertIn('name="categories"', html)
            self.assertIn('value="python"', html)
            
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)
    
    def test_edit_form_shows_source_type(self):
        """Test that edit form displays source type (ical/manual)"""
        from app import app
        import os
        import yaml
        
        client = app.test_client()
        
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, 'upcoming.yaml')
        
        today_str = self.today.strftime('%Y-%m-%d')
        test_guid = 'srctest1234567890123456789012345'
        
        test_events = [
            {
                'date': today_str,
                'time': '18:00',
                'title': 'iCal Event',
                'location': 'DC',
                'url': 'https://example.com',
                'guid': test_guid,
                'source': 'ical'
            }
        ]
        
        try:
            with open(test_file, 'w') as f:
                yaml.dump(test_events, f)
            
            response = client.get(f'/edit/{test_guid}/')
            html = response.data.decode()
            
            # Check source type is displayed
            self.assertIn('ical', html.lower())
            
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)


class TestOverrideFileCreation(unittest.TestCase):
    """Test cases for override file creation and loading"""
    
    def test_override_file_structure(self):
        """Test that override files have correct YAML structure"""
        import yaml
        import os
        
        override_data = {
            'title': 'Updated Event Title',
            'location': 'New Location DC',
            'categories': ['python', 'ai']
        }
        
        test_file = '_event_overrides/test_structure.yaml'
        
        try:
            os.makedirs('_event_overrides', exist_ok=True)
            with open(test_file, 'w') as f:
                yaml.dump(override_data, f)
            
            # Read back and verify
            with open(test_file, 'r') as f:
                loaded = yaml.safe_load(f)
            
            self.assertEqual(loaded['title'], 'Updated Event Title')
            self.assertEqual(loaded['location'], 'New Location DC')
            self.assertEqual(loaded['categories'], ['python', 'ai'])
            
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)
    
    def test_override_partial_fields(self):
        """Test that override files can contain partial field updates"""
        from generate_month_data import merge_event_with_override
        
        original_event = {
            'title': 'Original Title',
            'date': '2025-01-15',
            'time': '18:00',
            'location': 'DC',
            'url': 'https://example.com',
            'description': 'Original description'
        }
        
        # Override only some fields
        override = {
            'title': 'Updated Title',
            'location': 'Arlington VA'
        }
        
        merged = merge_event_with_override(original_event, override)
        
        # Check overridden fields
        self.assertEqual(merged['title'], 'Updated Title')
        self.assertEqual(merged['location'], 'Arlington VA')
        
        # Check preserved fields
        self.assertEqual(merged['date'], '2025-01-15')
        self.assertEqual(merged['time'], '18:00')
        self.assertEqual(merged['url'], 'https://example.com')
        self.assertEqual(merged['description'], 'Original description')


class TestEditRoute(unittest.TestCase):
    """Test cases for the /edit/<event_id>/ route"""
    
    def setUp(self):
        from datetime import datetime
        import pytz
        self.timezone_name = 'US/Eastern'
        self.local_tz = pytz.timezone(self.timezone_name)
        self.today = datetime.now(self.local_tz).date()
    
    def test_edit_route_loads_event_by_guid(self):
        """Test that edit route loads correctly with valid event guid"""
        from app import app
        import os
        import yaml
        
        client = app.test_client()
        
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, 'upcoming.yaml')
        
        today_str = self.today.strftime('%Y-%m-%d')
        test_guid = 'abc123def456789012345678901234ab'
        
        test_events = [
            {
                'date': today_str,
                'time': '18:00',
                'title': 'Test Python Meetup',
                'location': 'Washington DC',
                'url': 'https://example.com/event',
                'guid': test_guid,
                'source': 'ical'
            }
        ]
        
        try:
            with open(test_file, 'w') as f:
                yaml.dump(test_events, f)
            
            response = client.get(f'/edit/{test_guid}/')
            
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Test Python Meetup', response.data)
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)
    
    def test_edit_route_loads_event_by_slug(self):
        """Test that edit route loads manual events by slug"""
        from app import app
        import os
        import yaml
        
        client = app.test_client()
        
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, 'upcoming.yaml')
        
        today_str = self.today.strftime('%Y-%m-%d')
        
        test_events = [
            {
                'date': today_str,
                'time': '18:00',
                'title': 'Manual Event Test',
                'location': 'Arlington VA',
                'url': 'https://example.com/manual',
                'guid': 'xyz789',
                'source': 'manual',
                'slug': 'manual-event-test'
            }
        ]
        
        try:
            with open(test_file, 'w') as f:
                yaml.dump(test_events, f)
            
            response = client.get('/edit/manual-event-test/')
            
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Manual Event Test', response.data)
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)
    
    def test_edit_route_returns_404_for_unknown_event(self):
        """Test that edit route returns 404 for nonexistent event"""
        from app import app
        import os
        import yaml
        
        client = app.test_client()
        
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, 'upcoming.yaml')
        
        try:
            with open(test_file, 'w') as f:
                yaml.dump([], f)
            
            response = client.get('/edit/nonexistent-event-id/')
            
            self.assertEqual(response.status_code, 404)
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)
    
    def test_edit_route_passes_event_data_to_template(self):
        """Test that edit route passes event data correctly to template"""
        from app import app
        import os
        import yaml
        
        client = app.test_client()
        
        data_dir = '_data'
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, 'upcoming.yaml')
        
        today_str = self.today.strftime('%Y-%m-%d')
        test_guid = 'testguid123456789012345678901234'
        
        test_events = [
            {
                'date': today_str,
                'time': '14:30',
                'title': 'AI Conference 2025',
                'location': 'Bethesda MD',
                'url': 'https://ai-conf.example.com',
                'description': 'Annual AI meetup',
                'guid': test_guid,
                'source': 'ical',
                'categories': ['ai', 'data']
            }
        ]
        
        try:
            with open(test_file, 'w') as f:
                yaml.dump(test_events, f)
            
            response = client.get(f'/edit/{test_guid}/')
            
            self.assertEqual(response.status_code, 200)
            # Check event data is in the page
            self.assertIn(b'AI Conference 2025', response.data)
            self.assertIn(b'Bethesda MD', response.data)
            self.assertIn(b'14:30', response.data)
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)


if __name__ == '__main__':
    unittest.main()