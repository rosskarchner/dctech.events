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

    def test_no_events_returns_none(self):
        text = social_posting.create_post_text([], date(2026, 4, 7))
        self.assertIsNone(text)

    def test_url_included_in_post(self):
        events = [self._make_event('My Event')]
        target = date(2026, 4, 7)
        text = social_posting.create_post_text(events, target)
        self.assertIn('https://dctech.events', text)


class TestGetMicropubConfig(unittest.TestCase):
    def test_success_returns_config(self):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {'destination': [{'uid': 'https://example.micro.blog/'}]}
        with patch('social_posting.requests.get', return_value=mock_response):
            result = social_posting.get_micropub_config('token123')
        self.assertEqual(result, {'destination': [{'uid': 'https://example.micro.blog/'}]})

    def test_401_returns_none_and_logs_hint(self):
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.text = 'Unauthorized'
        with patch('social_posting.requests.get', return_value=mock_response):
            with patch('builtins.print') as mock_print:
                result = social_posting.get_micropub_config('badtoken')
        self.assertIsNone(result)
        printed = ' '.join(str(call) for call in mock_print.call_args_list)
        self.assertIn('Hint', printed)

    def test_network_error_returns_none(self):
        import requests
        with patch('social_posting.requests.get', side_effect=requests.exceptions.ConnectionError('fail')):
            result = social_posting.get_micropub_config('token123')
        self.assertIsNone(result)


class TestPostToMicroblog(unittest.TestCase):
    def _mock_config_success(self, destinations=None):
        """Return a get_micropub_config mock that yields a config with destinations."""
        dest_list = destinations or [{'uid': 'https://test.micro.blog/'}]
        return patch('social_posting.get_micropub_config', return_value={'destination': dest_list})

    def _mock_config_failure(self):
        """Return a get_micropub_config mock that simulates a failed config query."""
        return patch('social_posting.get_micropub_config', return_value=None)

    def test_success_returns_true(self):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.ok = True
        with self._mock_config_failure():
            with patch('social_posting.requests.post', return_value=mock_response):
                result = social_posting.post_to_microblog('Hello', 'token123')
        self.assertTrue(result)

    def test_uses_destination_from_config(self):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.ok = True
        destinations = [{'uid': 'https://myblog.micro.blog/'}]
        with self._mock_config_success(destinations):
            with patch('social_posting.requests.post', return_value=mock_response) as mock_post:
                social_posting.post_to_microblog('Hello', 'token123')
        call_data = mock_post.call_args[1]['data']
        self.assertEqual(call_data.get('mp-destination'), 'https://myblog.micro.blog/')

    def test_env_destination_matched_from_config(self):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.ok = True
        destinations = [
            {'uid': 'https://blog-a.micro.blog/'},
            {'uid': 'https://blog-b.micro.blog/'},
        ]
        with self._mock_config_success(destinations):
            with patch.dict(os.environ, {'MP_DESTINATION': 'https://blog-b.micro.blog/'}):
                with patch('social_posting.requests.post', return_value=mock_response) as mock_post:
                    social_posting.post_to_microblog('Hello', 'token123')
        call_data = mock_post.call_args[1]['data']
        self.assertEqual(call_data.get('mp-destination'), 'https://blog-b.micro.blog/')

    def test_fallback_env_destination_when_no_config(self):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.ok = True
        with self._mock_config_failure():
            with patch.dict(os.environ, {'MP_DESTINATION': 'https://fallback.micro.blog/'}):
                with patch('social_posting.requests.post', return_value=mock_response) as mock_post:
                    social_posting.post_to_microblog('Hello', 'token123')
        call_data = mock_post.call_args[1]['data']
        self.assertEqual(call_data.get('mp-destination'), 'https://fallback.micro.blog/')

    def test_400_returns_false_and_logs_body(self):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.ok = False
        mock_response.reason = 'Bad Request'
        mock_response.text = 'Invalid token'
        with self._mock_config_failure():
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
        with self._mock_config_failure():
            with patch('social_posting.requests.post', return_value=mock_response):
                result = social_posting.post_to_microblog('Hello', 'token123')
        self.assertTrue(result)

    def test_no_token_returns_false(self):
        result = social_posting.post_to_microblog('Hello', None)
        self.assertFalse(result)

    def test_network_error_returns_false(self):
        import requests
        with self._mock_config_failure():
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

    def test_main_strips_whitespace_from_token(self):
        """A token with surrounding whitespace should be stripped before use."""
        with patch.dict(os.environ, {'MICROBLOG_TOKEN': '  tok  '}):
            with patch('social_posting.datetime') as mock_dt:
                mock_dt.now.return_value.date.return_value = date(2026, 4, 7)
                with patch('os.path.exists', return_value=True):
                    with patch('json.load', return_value=self._mock_events()):
                        with patch('builtins.open', unittest.mock.mock_open()):
                            with patch('social_posting.post_to_microblog', return_value=True) as mock_post:
                                social_posting.main()
        # post_to_microblog should have received the stripped token
        called_token = mock_post.call_args[0][1]
        self.assertEqual(called_token, 'tok')

    def test_main_exits_1_on_blank_token(self):
        """A whitespace-only token should be treated as missing."""
        with patch.dict(os.environ, {'MICROBLOG_TOKEN': '   '}):
            with self.assertRaises(SystemExit) as cm:
                social_posting.main()
        self.assertEqual(cm.exception.code, 1)


if __name__ == '__main__':
    unittest.main()
