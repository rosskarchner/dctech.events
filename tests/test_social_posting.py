#!/usr/bin/env python3
import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from datetime import date

# Ensure the scripts directory is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import social_posting


class TestCreatePostText(unittest.TestCase):
    def _make_event(self, title):
        return {'title': title, 'date': '2026-04-07'}

    def test_single_event_within_limit(self):
        events = [self._make_event('Short Event')]
        target = date(2026, 4, 7)
        text = social_posting.create_post_text(events, target)
        self.assertIsNotNone(text)
        self.assertIn('Short Event', text)
        self.assertLessEqual(len(text), social_posting.CHAR_LIMIT)

    def test_single_long_event_truncated(self):
        events = [self._make_event('A' * 400)]
        target = date(2026, 4, 7)
        text = social_posting.create_post_text(events, target)
        self.assertIsNotNone(text)
        self.assertLessEqual(len(text), social_posting.CHAR_LIMIT)
        self.assertTrue(text.endswith('...') or len(text) <= social_posting.CHAR_LIMIT)

    def test_multiple_events_truncated_to_fit(self):
        events = [self._make_event(f'Event Title Number {i} With Extra Words') for i in range(20)]
        target = date(2026, 4, 7)
        text = social_posting.create_post_text(events, target)
        self.assertIsNotNone(text)
        self.assertLessEqual(len(text), social_posting.CHAR_LIMIT)

    def test_html_entities_in_title_are_decoded(self):
        events = [self._make_event('Event &amp; Conference')]
        target = date(2026, 4, 7)
        text = social_posting.create_post_text(events, target)
        self.assertIsNotNone(text)
        self.assertIn('Event & Conference', text)
        self.assertNotIn('&amp;', text)
        self.assertLessEqual(len(text), social_posting.CHAR_LIMIT)


        text = social_posting.create_post_text([], date(2026, 4, 7))
        self.assertIsNone(text)

    def test_url_included_in_post(self):
        events = [self._make_event('My Event')]
        target = date(2026, 4, 7)
        text = social_posting.create_post_text(events, target)
        self.assertIn('https://dctech.events', text)


class TestPostToMicroblog(unittest.TestCase):
    def test_success_returns_true(self):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.ok = True
        with patch('social_posting.requests.post', return_value=mock_response):
            result = social_posting.post_to_microblog('Hello', 'token123')
        self.assertTrue(result)

    def test_400_returns_false_and_logs_body(self):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.ok = False
        mock_response.reason = 'Bad Request'
        mock_response.text = 'Invalid token'
        with patch('social_posting.requests.post', return_value=mock_response):
            with patch('builtins.print') as mock_print:
                result = social_posting.post_to_microblog('Hello', 'token123')
        self.assertFalse(result)
        printed = ' '.join(str(call) for call in mock_print.call_args_list)
        self.assertIn('400', printed)
        self.assertIn('Invalid token', printed)

    def test_500_returns_true_with_warning(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.ok = False
        with patch('social_posting.requests.post', return_value=mock_response):
            result = social_posting.post_to_microblog('Hello', 'token123')
        self.assertTrue(result)

    def test_no_token_returns_false(self):
        result = social_posting.post_to_microblog('Hello', None)
        self.assertFalse(result)

    def test_network_error_returns_false(self):
        import requests
        with patch('social_posting.requests.post', side_effect=requests.exceptions.ConnectionError('fail')):
            result = social_posting.post_to_microblog('Hello', 'token123')
        self.assertFalse(result)


class TestMain(unittest.TestCase):
    def _mock_events(self):
        return [
            {'title': 'My Event', 'date': '2026-04-07', 'location': 'Washington DC'}
        ]

    def test_main_exits_1_on_post_failure(self):
        with patch.dict(os.environ, {'MICROBLOG_TOKEN': 'tok'}):
            with patch('social_posting.datetime') as mock_dt:
                mock_dt.now.return_value.date.return_value = date(2026, 4, 7)
                with patch('builtins.open', unittest.mock.mock_open(read_data='[]')):
                    with patch('os.path.exists', return_value=True):
                        with patch('json.load', return_value=self._mock_events()):
                            with patch('social_posting.post_to_microblog', return_value=False):
                                with self.assertRaises(SystemExit) as cm:
                                    social_posting.main()
                                self.assertEqual(cm.exception.code, 1)

    def test_main_does_not_exit_on_success(self):
        with patch.dict(os.environ, {'MICROBLOG_TOKEN': 'tok'}):
            with patch('social_posting.datetime') as mock_dt:
                mock_dt.now.return_value.date.return_value = date(2026, 4, 7)
                with patch('os.path.exists', return_value=True):
                    with patch('json.load', return_value=self._mock_events()):
                        with patch('builtins.open', unittest.mock.mock_open()):
                            with patch('social_posting.post_to_microblog', return_value=True):
                                # Should not raise SystemExit
                                try:
                                    social_posting.main()
                                except SystemExit:
                                    self.fail("main() raised SystemExit on success")


if __name__ == '__main__':
    unittest.main()
