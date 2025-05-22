#!/usr/bin/env python3
import unittest
from datetime import datetime, date, timedelta
import pytz
from app import get_next_week_and_month_dates

class TestApp(unittest.TestCase):
    def setUp(self):
        self.timezone_name = 'US/Eastern'
        self.local_tz = pytz.timezone(self.timezone_name)
        self.today = datetime.now(self.local_tz).date()
    
    def test_get_next_week_and_month_dates_with_events(self):
        """Test that get_next_week_and_month_dates returns correct dates when events exist"""
        # Create test events
        next_week = self.today + timedelta(days=7)
        next_month = date(self.today.year if self.today.month < 12 else self.today.year + 1,
                         self.today.month + 1 if self.today.month < 12 else 1,
                         1)
        
        events = [
            {'date': (self.today + timedelta(days=5)).strftime('%Y-%m-%d')},
            {'date': (self.today + timedelta(days=8)).strftime('%Y-%m-%d')},
            {'date': next_month.strftime('%Y-%m-%d')},
            {'date': (next_month + timedelta(days=5)).strftime('%Y-%m-%d')}
        ]
        
        next_week_date, next_month_date = get_next_week_and_month_dates(events)
        
        # The function should return the closest future dates to next week and next month
        self.assertEqual(next_week_date, (self.today + timedelta(days=8)).strftime('%Y-%m-%d'))
        self.assertEqual(next_month_date, next_month.strftime('%Y-%m-%d'))
    
    def test_get_next_week_and_month_dates_no_events(self):
        """Test that get_next_week_and_month_dates returns target dates when no events exist"""
        events = []
        
        next_week_date, next_month_date = get_next_week_and_month_dates(events)
        
        # Should return the target dates
        expected_next_week = (self.today + timedelta(days=7)).strftime('%Y-%m-%d')
        expected_next_month = date(
            self.today.year if self.today.month < 12 else self.today.year + 1,
            self.today.month + 1 if self.today.month < 12 else 1,
            1
        ).strftime('%Y-%m-%d')
        
        self.assertEqual(next_week_date, expected_next_week)
        self.assertEqual(next_month_date, expected_next_month)
    
    def test_get_next_week_and_month_dates_invalid_dates(self):
        """Test that get_next_week_and_month_dates handles invalid dates gracefully"""
        events = [
            {'date': 'invalid-date'},
            {'date': (self.today + timedelta(days=8)).strftime('%Y-%m-%d')},
            {'date': 'not-a-date'}
        ]
        
        next_week_date, next_month_date = get_next_week_and_month_dates(events)
        
        # Should still work with the one valid date
        self.assertEqual(next_week_date, (self.today + timedelta(days=8)).strftime('%Y-%m-%d'))
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
        self.assertEqual(len(time_slots), 3)  # 9am, 2:30pm, and TBD
        
        # Verify time slot order and content
        self.assertEqual(time_slots[0]['time'], '9:00 am')
        self.assertEqual(len(time_slots[0]['events']), 2)
        self.assertEqual(time_slots[1]['time'], '2:30 pm')
        self.assertEqual(len(time_slots[1]['events']), 1)
        self.assertEqual(time_slots[2]['time'], 'TBD')
        self.assertEqual(len(time_slots[2]['events']), 1)
        
        # Verify events are sorted by title within time slots
        morning_events = time_slots[0]['events']
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

if __name__ == '__main__':
    unittest.main()