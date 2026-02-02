#!/usr/bin/env python3
"""
Tests for post_newsletter_to_microblog.py — form-encoded note-style Micropub.
"""
import pytest
from datetime import date
from unittest.mock import Mock, patch
import post_newsletter_to_microblog


class TestWeekIdentifier:
    """Tests for ISO week identifier generation."""

    def test_week_identifier_normal(self):
        # Monday Feb 3, 2026 is ISO week 6
        assert post_newsletter_to_microblog.get_week_identifier(date(2026, 2, 3)) == "2026-W06"

    def test_week_identifier_week_one(self):
        # Jan 1 2026 is a Thursday → ISO week 1
        assert post_newsletter_to_microblog.get_week_identifier(date(2026, 1, 1)) == "2026-W01"

    def test_week_identifier_year_boundary(self):
        # Dec 31, 2025 is a Wednesday → ISO week 1 of 2026
        assert post_newsletter_to_microblog.get_week_identifier(date(2025, 12, 31)) == "2026-W01"

    def test_week_identifier_pads_single_digit(self):
        result = post_newsletter_to_microblog.get_week_identifier(date(2026, 1, 5))
        assert result == "2026-W02"
        assert "-W02" in result  # zero-padded


class TestWeekUrl:
    """Tests for week URL generation."""

    def test_week_url_format(self):
        url = post_newsletter_to_microblog.get_week_url(date(2026, 2, 3))
        assert url == "https://dctech.events/week/2026-W06/"

    def test_week_url_includes_trailing_slash(self):
        url = post_newsletter_to_microblog.get_week_url(date(2026, 2, 3))
        assert url.endswith("/")


class TestFormatShortDate:
    """Tests for M/D/YY date formatting."""

    def test_no_leading_zeros(self):
        assert post_newsletter_to_microblog.format_short_date(date(2026, 2, 3)) == "2/3/26"

    def test_double_digit_month_day(self):
        assert post_newsletter_to_microblog.format_short_date(date(2026, 11, 15)) == "11/15/26"

    def test_single_digit_day(self):
        assert post_newsletter_to_microblog.format_short_date(date(2026, 1, 1)) == "1/1/26"


class TestNoteContent:
    """Tests for note content generation."""

    def test_note_content_format(self):
        content = post_newsletter_to_microblog.generate_note_content(date(2026, 2, 3))
        assert content == "DC Tech Events for the week of 2/3/26: https://dctech.events/week/2026-W06/"

    def test_note_content_contains_url(self):
        content = post_newsletter_to_microblog.generate_note_content(date(2026, 2, 3))
        assert "https://dctech.events/week/" in content

    def test_note_content_contains_site_name(self):
        content = post_newsletter_to_microblog.generate_note_content(date(2026, 2, 3))
        assert "DC Tech Events" in content


class TestMicropubFormEncoded:
    """Tests for form-encoded Micropub posting."""

    @patch('post_newsletter_to_microblog.requests.post')
    def test_post_uses_form_encoding(self, mock_post):
        """Payload sent via data= (form-encoded), not json=."""
        mock_response = Mock()
        mock_response.headers = {'Location': 'https://micro.blog/posts/123'}
        mock_post.return_value = mock_response

        post_newsletter_to_microblog.post_to_microblog(
            content='Test content',
            token='fake-token',
            dry_run=False
        )

        call_args = mock_post.call_args
        # Must use data= kwarg (form-encoded), not json=
        assert 'data' in call_args[1]
        assert 'json' not in call_args[1]

    @patch('post_newsletter_to_microblog.requests.post')
    def test_post_has_h_entry(self, mock_post):
        mock_response = Mock()
        mock_response.headers = {}
        mock_post.return_value = mock_response

        post_newsletter_to_microblog.post_to_microblog(
            content='Test', token='fake-token'
        )

        data = mock_post.call_args[1]['data']
        assert data['h'] == 'entry'

    @patch('post_newsletter_to_microblog.requests.post')
    def test_post_has_no_name(self, mock_post):
        """Note-style post should not include a 'name' field."""
        mock_response = Mock()
        mock_response.headers = {}
        mock_post.return_value = mock_response

        post_newsletter_to_microblog.post_to_microblog(
            content='Test', token='fake-token'
        )

        data = mock_post.call_args[1]['data']
        assert 'name' not in data

    @patch('post_newsletter_to_microblog.requests.post')
    def test_post_content_is_plain_text(self, mock_post):
        mock_response = Mock()
        mock_response.headers = {}
        mock_post.return_value = mock_response

        post_newsletter_to_microblog.post_to_microblog(
            content='DC Tech Events for the week of 2/3/26: https://dctech.events/week/2026-W06/',
            token='fake-token'
        )

        data = mock_post.call_args[1]['data']
        assert data['content'] == 'DC Tech Events for the week of 2/3/26: https://dctech.events/week/2026-W06/'

    @patch('post_newsletter_to_microblog.requests.post')
    def test_post_with_destination(self, mock_post):
        mock_response = Mock()
        mock_response.headers = {}
        mock_post.return_value = mock_response

        post_newsletter_to_microblog.post_to_microblog(
            content='Test',
            token='fake-token',
            destination='https://updates.dctech.events/'
        )

        data = mock_post.call_args[1]['data']
        assert data['mp-destination'] == 'https://updates.dctech.events/'

    @patch('post_newsletter_to_microblog.requests.post')
    def test_post_without_destination(self, mock_post):
        mock_response = Mock()
        mock_response.headers = {}
        mock_post.return_value = mock_response

        post_newsletter_to_microblog.post_to_microblog(
            content='Test', token='fake-token'
        )

        data = mock_post.call_args[1]['data']
        assert 'mp-destination' not in data

    def test_dry_run_returns_true(self):
        result = post_newsletter_to_microblog.post_to_microblog(
            content='Test', token='fake-token', dry_run=True
        )
        assert result is True

    def test_no_token_returns_false(self):
        result = post_newsletter_to_microblog.post_to_microblog(
            content='Test', token=None
        )
        assert result is False

    @patch('post_newsletter_to_microblog.requests.post')
    def test_successful_post_returns_true(self, mock_post):
        mock_response = Mock()
        mock_response.headers = {'Location': 'https://micro.blog/posts/123'}
        mock_post.return_value = mock_response

        result = post_newsletter_to_microblog.post_to_microblog(
            content='Test', token='fake-token'
        )
        assert result is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
