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

if __name__ == '__main__':
    unittest.main()