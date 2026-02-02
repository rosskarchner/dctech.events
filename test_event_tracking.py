#!/usr/bin/env python3
"""
Tests for event tracking and RSS feed functionality.
"""
import os
import sys
import json
import yaml
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

# Import modules to test
import track_events
import generate_rss_feed
import post_daily_event_summary


class TestTrackEvents:
    """Tests for track_events.py"""
    
    def test_get_event_key_with_guid(self):
        """Test event key generation for iCal events with guid"""
        event = {'guid': 'abc123', 'title': 'Test Event'}
        key = track_events.get_event_key(event)
        assert key == 'guid:abc123'
    
    def test_get_event_key_with_id(self):
        """Test event key generation for manual events with id"""
        event = {'id': 'event-123', 'title': 'Test Event'}
        key = track_events.get_event_key(event)
        assert key == 'id:event-123'
    
    def test_get_event_key_fallback(self):
        """Test event key generation fallback for events without guid or id"""
        event = {
            'date': '2026-02-15',
            'time': '10:00',
            'title': 'Test Event'
        }
        key = track_events.get_event_key(event)
        assert key.startswith('event:2026-02-15:10:00:Test Event')
    
    def test_compare_events_finds_new_events(self):
        """Test that compare_events correctly identifies new events"""
        previous_events = [
            {'guid': 'abc123', 'title': 'Event 1'},
        ]
        current_events = [
            {'guid': 'abc123', 'title': 'Event 1'},
            {'guid': 'def456', 'title': 'Event 2'},
        ]
        
        new_events = track_events.compare_events(current_events, previous_events)
        
        assert len(new_events) == 1
        assert new_events[0]['guid'] == 'def456'
    
    def test_compare_events_no_previous(self):
        """Test compare_events with no previous events"""
        current_events = [
            {'guid': 'abc123', 'title': 'Event 1'},
            {'guid': 'def456', 'title': 'Event 2'},
        ]
        
        new_events = track_events.compare_events(current_events, [])
        
        assert len(new_events) == 2
    
    def test_update_metadata(self):
        """Test metadata update with new events"""
        metadata = {
            'guid:abc123': {
                'first_seen': '2026-01-01T00:00:00+00:00',
                'title': 'Event 1',
                'date': '2026-02-01',
                'url': 'https://example.com/1'
            }
        }
        
        new_events = [
            {
                'guid': 'def456',
                'title': 'Event 2',
                'date': '2026-02-15',
                'url': 'https://example.com/2'
            }
        ]
        
        updated_metadata, count = track_events.update_metadata(metadata, new_events)
        
        assert count == 1
        assert 'guid:def456' in updated_metadata
        assert updated_metadata['guid:def456']['title'] == 'Event 2'
        assert 'first_seen' in updated_metadata['guid:def456']


class TestGenerateRSSFeed:
    """Tests for generate_rss_feed.py"""
    
    def test_get_recent_events(self):
        """Test filtering events by date"""
        now = datetime.now(timezone.utc)
        old_date = (now - timedelta(days=40)).isoformat()
        recent_date = (now - timedelta(days=5)).isoformat()
        
        metadata = {
            'event1': {
                'first_seen': old_date,
                'title': 'Old Event',
                'date': '2026-01-01'
            },
            'event2': {
                'first_seen': recent_date,
                'title': 'Recent Event',
                'date': '2026-02-15'
            }
        }
        
        recent_events = generate_rss_feed.get_recent_events(metadata, days=30)
        
        assert len(recent_events) == 1
        assert recent_events[0][1]['title'] == 'Recent Event'
    
    def test_generate_rss_feed_structure(self):
        """Test RSS feed XML structure"""
        events = [
            ('event1', {
                'first_seen': datetime.now(timezone.utc).isoformat(),
                'title': 'Test Event',
                'date': '2026-02-15',
                'url': 'https://example.com/event'
            })
        ]
        
        rss_xml = generate_rss_feed.generate_rss_feed(events, max_items=10)
        
        assert '<?xml version' in rss_xml
        assert '<rss version="2.0"' in rss_xml
        assert '<channel>' in rss_xml
        assert 'DC Tech Events - New Events' in rss_xml
        assert 'Test Event' in rss_xml
        assert 'https://example.com/event' in rss_xml
    
    def test_generate_rss_feed_respects_max_items(self):
        """Test that RSS feed respects max_items limit"""
        now = datetime.now(timezone.utc).isoformat()
        events = [
            (f'event{i}', {
                'first_seen': now,
                'title': f'Event {i}',
                'date': '2026-02-15',
                'url': f'https://example.com/event{i}'
            })
            for i in range(20)
        ]
        
        rss_xml = generate_rss_feed.generate_rss_feed(events, max_items=5)
        
        # Count number of <item> tags
        item_count = rss_xml.count('<item>')
        assert item_count == 5


class TestPostDailyEventSummary:
    """Tests for post_daily_event_summary.py"""
    
    def test_get_todays_new_events(self):
        """Test filtering events by date"""
        import pytz
        local_tz = pytz.timezone('US/Eastern')
        today = datetime.now(local_tz).date()
        yesterday = today - timedelta(days=1)
        
        # Create timestamps - use noon to avoid DST edge cases
        today_dt = local_tz.localize(datetime.combine(today, datetime.min.time().replace(hour=12)))
        yesterday_dt = local_tz.localize(datetime.combine(yesterday, datetime.min.time().replace(hour=12)))
        
        today_timestamp = today_dt.astimezone(timezone.utc).isoformat()
        yesterday_timestamp = yesterday_dt.astimezone(timezone.utc).isoformat()
        
        metadata = {
            'event1': {
                'first_seen': yesterday_timestamp,
                'title': 'Yesterday Event',
                'date': '2026-02-15'
            },
            'event2': {
                'first_seen': today_timestamp,
                'title': 'Today Event',
                'date': '2026-02-20'
            }
        }
        
        todays_events = post_daily_event_summary.get_todays_new_events(metadata, target_date=today)
        
        assert len(todays_events) == 1
        assert todays_events[0]['title'] == 'Today Event'
    
    def test_generate_title(self):
        """Test post title generation"""
        from datetime import date
        
        # Test various dates for ordinal suffixes
        test_date = date(2026, 5, 3)
        title = post_daily_event_summary.generate_title(5, test_date)
        assert title == '5 new events added on May 3rd 2026'
        
        test_date = date(2026, 5, 1)
        title = post_daily_event_summary.generate_title(1, test_date)
        assert title == '1 new event added on May 1st 2026'
        
        test_date = date(2026, 5, 22)
        title = post_daily_event_summary.generate_title(3, test_date)
        assert title == '3 new events added on May 22nd 2026'
    
    def test_generate_summary_html(self):
        """Test HTML summary generation"""
        from datetime import date
        
        events = [
            {
                'title': 'Event 1',
                'date': '2026-02-15',
                'url': 'https://example.com/1'
            },
            {
                'title': 'Event 2',
                'date': '2026-02-20',
                'url': 'https://example.com/2'
            }
        ]
        
        html = post_daily_event_summary.generate_summary_html(events, date(2026, 2, 1))
        
        assert '2 new events have been added' in html
        assert 'Event 1' in html
        assert 'Event 2' in html
        assert 'https://example.com/1' in html
        assert 'https://example.com/2' in html
        assert '<ul>' in html
        assert '</ul>' in html
    
    @patch('post_daily_event_summary.requests.post')
    def test_post_to_microblog_dry_run(self, mock_post):
        """Test posting to microblog in dry run mode"""
        result = post_daily_event_summary.post_to_microblog(
            title='Test Title',
            content='<p>Test Content</p>',
            token='fake-token',
            dry_run=True
        )
        
        assert result is True
        assert not mock_post.called
    
    @patch('post_daily_event_summary.requests.post')
    def test_post_to_microblog_success(self, mock_post):
        """Test successful posting to microblog with form-encoded payload"""
        mock_response = Mock()
        mock_response.headers = {'Location': 'https://micro.blog/posts/123'}
        mock_post.return_value = mock_response

        result = post_daily_event_summary.post_to_microblog(
            title='Test Title',
            content='<p>Test Content</p>',
            token='fake-token',
            dry_run=False
        )

        assert result is True
        assert mock_post.called
        call_args = mock_post.call_args
        # Check form-encoded payload
        data = call_args[1]['data']
        assert data['h'] == 'entry'
        assert data['name'] == 'Test Title'
        assert data['content[html]'] == '<p>Test Content</p>'
        # Should use data= not json=
        assert 'json' not in call_args[1]

    @patch('post_daily_event_summary.requests.post')
    def test_post_to_microblog_with_destination(self, mock_post):
        """Test posting with mp-destination as form param"""
        mock_response = Mock()
        mock_response.headers = {'Location': 'https://micro.blog/posts/123'}
        mock_post.return_value = mock_response

        result = post_daily_event_summary.post_to_microblog(
            title='Test Title',
            content='<p>Test Content</p>',
            token='fake-token',
            destination='https://updates.dctech.events/',
            dry_run=False
        )

        assert result is True
        data = mock_post.call_args[1]['data']
        assert data['mp-destination'] == 'https://updates.dctech.events/'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
