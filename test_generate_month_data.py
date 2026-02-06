import unittest
from datetime import datetime, date, timedelta
import pytz
from generate_month_data import (
    is_event_in_allowed_states,
    are_events_duplicates,
    remove_duplicates,
    looks_like_url,
    sanitize_text,
    calculate_event_hash,
    process_events,
    parse_single_event_data
)

class TestGenerateMonthDataStandalone(unittest.TestCase):
    
    def test_looks_like_url(self):
        self.assertTrue(looks_like_url("http://example.com"))
        self.assertTrue(looks_like_url("https://example.com"))
        self.assertTrue(looks_like_url("www.example.com"))
        self.assertFalse(looks_like_url("example.com"))
        self.assertFalse(looks_like_url("not a url"))
        self.assertFalse(looks_like_url(None))

    def test_sanitize_text(self):
        self.assertEqual(sanitize_text(" hello "), " hello ")
        self.assertEqual(sanitize_text(None), "")
        self.assertEqual(sanitize_text(123), "123")

    def test_is_event_in_allowed_states(self):
        # No filter
        self.assertTrue(is_event_in_allowed_states({}, []))
        
        # Explicit allowed states
        allowed = ['DC', 'VA']
        
        # Structured location
        self.assertTrue(is_event_in_allowed_states({'location': 'Washington, DC'}, allowed))
        self.assertTrue(is_event_in_allowed_states({'location': 'Arlington, VA'}, allowed))
        self.assertFalse(is_event_in_allowed_states({'location': 'Baltimore, MD'}, allowed))
        
        # Regex matching
        self.assertTrue(is_event_in_allowed_states({'location': 'Some place in DC'}, allowed))
        self.assertTrue(is_event_in_allowed_states({'location': 'Some place in VA'}, allowed))
        self.assertFalse(is_event_in_allowed_states({'location': 'Some place in MD'}, allowed))
        
        # No location or unclear
        self.assertTrue(is_event_in_allowed_states({'location': ''}, allowed))
        self.assertTrue(is_event_in_allowed_states({'location': 'Online'}, allowed))
        
        # Invalid state codes (typos) - should assume DC when DC is in allowed states
        self.assertTrue(is_event_in_allowed_states({'location': 'Washington, DI'}, allowed))
        self.assertTrue(is_event_in_allowed_states({'location': 'Washington, XY'}, allowed))
        
        # Invalid state codes when DC is NOT in allowed states - should be rejected
        allowed_no_dc = ['VA', 'MD']
        self.assertFalse(is_event_in_allowed_states({'location': 'Washington, DI'}, allowed_no_dc))
        self.assertFalse(is_event_in_allowed_states({'location': 'Washington, XY'}, allowed_no_dc))

    def test_are_events_duplicates(self):
        e1 = {'title': 'Event A', 'date': '2023-01-01', 'time': '10:00'}
        e2 = {'title': 'Event A', 'date': '2023-01-01', 'time': '10:00'}
        e3 = {'title': 'Event B', 'date': '2023-01-01', 'time': '10:00'}
        e4 = {'title': 'Event A', 'date': '2023-01-02', 'time': '10:00'}
        
        self.assertTrue(are_events_duplicates(e1, e2))
        self.assertFalse(are_events_duplicates(e1, e3))
        self.assertFalse(are_events_duplicates(e1, e4))

    def test_remove_duplicates(self):
        # Regular duplicates
        e1 = {'title': 'Event A', 'date': '2023-01-01', 'time': '10:00', 'group': 'G1', 'group_website': 'w1'}
        e2 = {'title': 'Event A', 'date': '2023-01-01', 'time': '10:00', 'group': 'G2', 'group_website': 'w2'}
        e3 = {'title': 'Event B', 'date': '2023-01-01', 'time': '10:00'}
        
        events = [e1, e2, e3]
        unique = remove_duplicates(events)
        
        self.assertEqual(len(unique), 2)
        # e1 should be kept, e2 rolled up into e1
        self.assertEqual(unique[0]['title'], 'Event A')
        self.assertIn('also_published_by', unique[0])
        self.assertEqual(unique[0]['also_published_by'][0]['group'], 'G2')
        
        # Explicit duplicates
        guid_parent = 'parent-guid'
        e_parent = {'title': 'Parent', 'date': '2023-01-01', 'time': '10:00', 'guid': guid_parent}
        e_child = {'title': 'Child', 'duplicate_of': guid_parent, 'group': 'G_Child', 'group_website': 'w_child'}
        
        events = [e_parent, e_child]
        unique = remove_duplicates(events)
        
        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0]['guid'], guid_parent)
        self.assertIn('also_published_by', unique[0])
        self.assertEqual(unique[0]['also_published_by'][0]['group'], 'G_Child')

class TestProcessEvents(unittest.TestCase):
    def setUp(self):
        self.today = date(2025, 1, 1)
        self.categories = {'python': {'name': 'Python', 'slug': 'python'}}
        self.groups = [
            {'id': 'g1', 'name': 'Group 1', 'website': 'w1', 'active': True},
            {'id': 'g2', 'name': 'Group 2', 'website': 'w2', 'active': False} # Inactive
        ]
        
    def test_process_ical_events_basic(self):
        # Basic flow: active group, valid future event
        ical_events = {
            'g1': [
                {
                    'title': 'Future Event',
                    'date': '2025-01-10',
                    'time': '10:00',
                    'url': 'http://e1.com',
                    'location': 'DC'
                }
            ]
        }
        
        events = process_events(self.groups, self.categories, [], ical_events, ['DC'], today=self.today)
        
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['title'], 'Future Event')
        self.assertEqual(events[0]['group'], 'Group 1')
        self.assertEqual(events[0]['source'], 'ical')

    def test_process_inactive_group(self):
        # Inactive group events should be ignored
        ical_events = {
            'g2': [{'title': 'Event', 'date': '2025-01-10', 'url': 'u', 'location': 'DC'}]
        }
        
        events = process_events(self.groups, self.categories, [], ical_events, ['DC'], today=self.today)
        self.assertEqual(len(events), 0)

    def test_filter_past_events(self):
        # Events before today should be ignored
        ical_events = {
            'g1': [{'title': 'Past', 'date': '2024-12-31', 'url': 'u', 'location': 'DC'}]
        }
        events = process_events(self.groups, self.categories, [], ical_events, ['DC'], today=self.today)
        self.assertEqual(len(events), 0)

    def test_filter_too_far_future(self):
        # Events > 90 days in future should be ignored for iCal
        future_date = (self.today + timedelta(days=91)).strftime('%Y-%m-%d')
        ical_events = {
            'g1': [{'title': 'Far Future', 'date': future_date, 'url': 'u', 'location': 'DC'}]
        }
        events = process_events(self.groups, self.categories, [], ical_events, ['DC'], today=self.today)
        self.assertEqual(len(events), 0)

    def test_filter_allowed_states(self):
        # Location filtering
        ical_events = {
            'g1': [
                {'title': 'In DC', 'date': '2025-01-10', 'url': 'u1', 'location': 'Washington, DC'},
                {'title': 'In NY', 'date': '2025-01-10', 'url': 'u2', 'location': 'New York, NY'}
            ]
        }
        events = process_events(self.groups, self.categories, [], ical_events, ['DC'], today=self.today)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['title'], 'In DC')

    def test_single_events(self):
        # Single events are processed differently (no 90 day limit, different source)
        far_future_date = (self.today + timedelta(days=100)).strftime('%Y-%m-%d')
        single = [
            {'title': 'Manual Event', 'date': '2025-01-10', 'time': '10:00', 'url': 'u1', 'location': 'DC'},
            {'title': 'Far Future Manual', 'date': far_future_date, 'time': '10:00', 'url': 'u2', 'location': 'DC'}
        ]
        
        events = process_events(self.groups, self.categories, single, {}, ['DC'], today=self.today)
        
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]['title'], 'Manual Event')
        self.assertEqual(events[0]['source'], 'manual')
        self.assertEqual(events[1]['title'], 'Far Future Manual')

    def test_deduplication(self):
        # Deduplication across sources
        ical_events = {
            'g1': [{'title': 'Meetup', 'date': '2025-01-10', 'time': '18:00', 'url': 'u1', 'location': 'DC'}]
        }
        single = [{'title': 'Meetup', 'date': '2025-01-10', 'time': '18:00', 'url': 'u2', 'location': 'DC', 'group': 'Group 2'}]
        
        events = process_events(self.groups, self.categories, single, ical_events, ['DC'], today=self.today)
        
        self.assertEqual(len(events), 1)
        # The first one processed (iCal) is kept
        self.assertEqual(events[0]['title'], 'Meetup')
        self.assertEqual(events[0]['source'], 'ical')
        
    def test_suppress_urls(self):
        group_with_suppress = {
            'id': 'g_suppress', 'name': 'Suppressed', 'website': 'w', 'active': True,
            'suppress_urls': ['http://bad.com']
        }
        ical_events = {
            'g_suppress': [
                {'title': 'Good', 'date': '2025-01-10', 'url': 'http://good.com', 'location': 'DC'},
                {'title': 'Bad', 'date': '2025-01-10', 'url': 'http://bad.com', 'location': 'DC'}
            ]
        }
        
        events = process_events([group_with_suppress], self.categories, [], ical_events, ['DC'], today=self.today)
        
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['title'], 'Good')

class TestParseSingleEventData(unittest.TestCase):
    def test_valid_event_parsing(self):
        event_data = {
            'title': 'Test Event',
            'date': '2025-01-01',
            'time': '10:00',
            'location': 'DC',
            'url': 'http://example.com'
        }
        parsed = parse_single_event_data(event_data, 'test_id', 'US/Eastern')
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['id'], 'test_id')
        self.assertEqual(parsed['start_date'], '2025-01-01')
        self.assertEqual(parsed['start_time'], '10:00')

    def test_invalid_date(self):
        event_data = {
            'title': 'Test Event',
            'date': 'invalid-date',
            'time': '10:00'
        }
        with self.assertRaises(ValueError):
            parse_single_event_data(event_data, 'test_id', 'US/Eastern')

    def test_invalid_time(self):
        event_data = {
            'title': 'Test Event',
            'date': '2025-01-01',
            'time': 'invalid-time'
        }
        with self.assertRaises(ValueError):
            parse_single_event_data(event_data, 'test_id', 'US/Eastern')

if __name__ == '__main__':
    unittest.main()
