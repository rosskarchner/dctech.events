import os
import tempfile
import unittest
from datetime import datetime, date, timedelta
import pytz
from generate_month_data import (
    is_event_in_allowed_states,
    are_events_duplicates,
    remove_duplicates,
    calculate_event_hash,
    process_events,
    load_event_overrides,
)

class TestGenerateMonthDataStandalone(unittest.TestCase):
    
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
        
        # Invalid state codes (typos) - should assume DC when:
        # 1. DC is in allowed states AND
        # 2. City is Washington (any invalid state) OR state is in DC_TYPO_CODES
        self.assertTrue(is_event_in_allowed_states({'location': 'Washington, DI'}, allowed))
        self.assertTrue(is_event_in_allowed_states({'location': 'Washington, XY'}, allowed))  # Washington + any invalid state
        self.assertTrue(is_event_in_allowed_states({'location': 'Washington, CD'}, allowed))
        self.assertTrue(is_event_in_allowed_states({'location': 'Anywhere, DI'}, allowed))  # DI in DC_TYPO_CODES
        
        # Valid state codes are checked normally, even for Washington city
        # (Note: There's a Washington state, but unlikely to be confused with Washington, DC)
        allowed_dc_only = ['DC']
        self.assertFalse(is_event_in_allowed_states({'location': 'Washington, MD'}, allowed_dc_only))
        self.assertTrue(is_event_in_allowed_states({'location': 'Washington, DC'}, allowed_dc_only))
        
        # Invalid state codes that are NOT DC typos - should be rejected
        self.assertFalse(is_event_in_allowed_states({'location': 'Austin, TZ'}, allowed))
        self.assertFalse(is_event_in_allowed_states({'location': 'Seattle, XY'}, allowed))
        
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

    def test_group_category_change_overrides_cached_categories(self):
        """Cached events must always reflect the group's current categories.

        If a category is removed from a group's YAML file, the next
        generate_month_data run should NOT include that category on the
        group's events — even if the iCal cache still has the old value.
        """
        group_updated = {
            'id': 'g1', 'name': 'Group 1', 'website': 'w1', 'active': True,
            # 'cybersecurity' has been removed; group now has no categories
            'categories': [],
        }
        ical_events = {
            'g1': [
                {
                    'title': 'Security Talk',
                    'date': '2025-01-10',
                    'time': '18:00',
                    'url': 'http://e1.com',
                    'location': 'Washington, DC',
                    # Stale categories baked into the cache from a previous fetch
                    'categories': ['cybersecurity'],
                }
            ]
        }

        events = process_events([group_updated], self.categories, [], ical_events, ['DC'], today=self.today)

        self.assertEqual(len(events), 1)
        self.assertNotIn('cybersecurity', events[0].get('categories', []),
                         "Removed group category must not appear in processed events")
        self.assertEqual(events[0]['categories'], [])

    def test_group_categories_applied_to_ical_events(self):
        """Events from a group should inherit the group's current categories."""
        group_with_cats = {
            'id': 'g1', 'name': 'Group 1', 'website': 'w1', 'active': True,
            'categories': ['ai', 'data'],
        }
        ical_events = {
            'g1': [
                {
                    'title': 'AI Meetup',
                    'date': '2025-01-10',
                    'time': '18:00',
                    'url': 'http://e1.com',
                    'location': 'Washington, DC',
                    'categories': ['ai', 'data'],
                }
            ]
        }

        events = process_events([group_with_cats], self.categories, [], ical_events, ['DC'], today=self.today)

        self.assertEqual(len(events), 1)
        self.assertIn('ai', events[0].get('categories', []))
        self.assertIn('data', events[0].get('categories', []))

    def test_dict_time_field_does_not_crash(self):
        # Multi-day events with per-day time dicts should not cause a sort error
        single = [
            {
                'title': 'Multi-Day Conference',
                'date': '2025-01-20',
                'end_date': '2025-01-22',
                'time': {'2025-01-20': '09:00', '2025-01-21': '10:00', '2025-01-22': '10:00'},
                'url': 'http://conf.com',
                'location': 'Washington, DC',
            },
            {
                'title': 'Regular Event',
                'date': '2025-01-15',
                'time': '18:00',
                'url': 'http://event.com',
                'location': 'Washington, DC',
            },
        ]
        # Should not raise TypeError
        events = process_events(self.groups, self.categories, single, {}, ['DC'], today=self.today)
        self.assertEqual(len(events), 2)
        # Regular event on 2025-01-15 should come first
        self.assertEqual(events[0]['title'], 'Regular Event')
        self.assertEqual(events[1]['title'], 'Multi-Day Conference')


class TestEventOverrides(unittest.TestCase):
    def setUp(self):
        self.today = date(2025, 1, 1)
        self.categories = {}
        self.groups = [
            {'id': 'g1', 'name': 'Group 1', 'website': 'w1', 'active': True},
        ]

    def _make_ical_event(self, title, date_str, time_str='10:00', url='http://example.com'):
        return {
            'title': title,
            'date': date_str,
            'time': time_str,
            'url': url,
            'location': 'Washington, DC',
            'categories': [],
        }

    def test_override_categories(self):
        event = self._make_ical_event('Cyber Summit', '2025-01-10', url='http://cybersummit.com')
        guid = calculate_event_hash('2025-01-10', '10:00', 'Cyber Summit', 'http://cybersummit.com')

        overrides = {guid: {'categories': ['cybersecurity', 'govtech']}}
        events = process_events(
            self.groups, self.categories, [], {'g1': [event]}, [],
            today=self.today, event_overrides=overrides,
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['categories'], ['cybersecurity', 'govtech'])

    def test_override_title(self):
        event = self._make_ical_event('Old Title', '2025-01-10', url='http://example.com')
        guid = calculate_event_hash('2025-01-10', '10:00', 'Old Title', 'http://example.com')

        overrides = {guid: {'title': 'New Corrected Title'}}
        events = process_events(
            self.groups, self.categories, [], {'g1': [event]}, [],
            today=self.today, event_overrides=overrides,
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['title'], 'New Corrected Title')

    def test_override_both_title_and_categories(self):
        event = self._make_ical_event('AI Conf', '2025-01-15', url='http://aiconf.com')
        guid = calculate_event_hash('2025-01-15', '10:00', 'AI Conf', 'http://aiconf.com')

        overrides = {guid: {'title': 'AI Conference 2025', 'categories': ['ai', 'conferences']}}
        events = process_events(
            self.groups, self.categories, [], {'g1': [event]}, [],
            today=self.today, event_overrides=overrides,
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['title'], 'AI Conference 2025')
        self.assertEqual(events[0]['categories'], ['ai', 'conferences'])

    def test_no_override_leaves_event_unchanged(self):
        event = self._make_ical_event('Regular Event', '2025-01-10', url='http://regular.com')
        event['categories'] = ['social']

        events = process_events(
            self.groups, self.categories, [], {'g1': [event]}, [],
            today=self.today, event_overrides={},
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['title'], 'Regular Event')
        self.assertEqual(events[0]['categories'], ['social'])

    def test_none_overrides_parameter_uses_empty_dict(self):
        event = self._make_ical_event('Regular Event', '2025-01-10', url='http://regular.com')
        # Should not raise and should behave as no overrides
        events = process_events(
            self.groups, self.categories, [], {'g1': [event]}, [],
            today=self.today, event_overrides=None,
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['title'], 'Regular Event')

    def test_load_event_overrides_missing_dir(self):
        # Point override dir at a non-existent path by temporarily patching
        import generate_month_data as gmd
        original = gmd.EVENT_OVERRIDES_DIR
        try:
            gmd.EVENT_OVERRIDES_DIR = '/tmp/nonexistent_overrides_dir_xyz'
            result = load_event_overrides()
            self.assertEqual(result, {})
        finally:
            gmd.EVENT_OVERRIDES_DIR = original

    def test_load_event_overrides_from_directory(self):
        import generate_month_data as gmd

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write a valid override file
            guid = 'abc123def456abc123def456abc12345'
            override_path = os.path.join(tmpdir, f'{guid}.yaml')
            with open(override_path, 'w') as f:
                f.write('categories:\n  - cybersecurity\n  - govtech\n')

            original = gmd.EVENT_OVERRIDES_DIR
            try:
                gmd.EVENT_OVERRIDES_DIR = tmpdir
                result = load_event_overrides()
            finally:
                gmd.EVENT_OVERRIDES_DIR = original

        self.assertIn(guid, result)
        self.assertEqual(result[guid]['categories'], ['cybersecurity', 'govtech'])


if __name__ == '__main__':
    unittest.main()
