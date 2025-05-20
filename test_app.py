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

if __name__ == '__main__':
    unittest.main()