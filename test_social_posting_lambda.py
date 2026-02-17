import unittest
from datetime import date, datetime
import pytz
from lambdas.daily_summary.handler import get_events_for_date, create_post_text
from lambdas.new_events_summary.handler import generate_summary_content

class TestDailySummary(unittest.TestCase):
    def setUp(self):
        self.sample_events = [
            {'title': 'Event 1', 'date': '2026-02-17', 'time': '18:00'},
            {'title': 'Event 2', 'date': '2026-02-17', 'time': '19:00'},
            {'title': 'Multi-day', 'date': '2026-02-16', 'end_date': '2026-02-18'},
            {'title': 'Future', 'date': '2026-02-20'}
        ]

    def test_get_events_for_date(self):
        target = date(2026, 2, 17)
        events = get_events_for_date(self.sample_events, target)
        self.assertEqual(len(events), 3)
        titles = [e['title'] for e in events]
        self.assertIn('Event 1', titles)
        self.assertIn('Event 2', titles)
        self.assertIn('Multi-day', titles)

    def test_create_post_text_single(self):
        target = date(2026, 2, 17)
        events = [{'title': 'Solo Event'}]
        text = create_post_text(events, target)
        self.assertIn('Solo Event', text)
        self.assertIn('dctech.events', text)

    def test_create_post_text_multiple(self):
        target = date(2026, 2, 17)
        events = [{'title': 'E1'}, {'title': 'E2'}, {'title': 'E3'}]
        text = create_post_text(events, target)
        # The current implementation uses ", " joining for full list
        self.assertIn('E1, E2, E3', text)

    def test_create_post_text_truncation(self):
        target = date(2026, 2, 17)
        events = [{'title': 'A' * 300}]
        text = create_post_text(events, target)
        self.assertLessEqual(len(text), 300)
        self.assertIn('...', text)

class TestNewEventsSummary(unittest.TestCase):
    def test_generate_summary_content(self):
        target = date(2026, 2, 17)
        content = generate_summary_content(5, target)
        self.assertIn('5 new events added today', content)
        self.assertIn('/just-added/#2-17-2026', content)

if __name__ == '__main__':
    unittest.main()
