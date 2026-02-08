#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import os
import sys

# Mock db_utils before importing generate_rss_feed
sys.modules['db_utils'] = MagicMock()

import generate_rss_feed

class TestGenerateRSSFeed(unittest.TestCase):
    def setUp(self):
        self.site_name = "Test Site"
        self.base_url = "https://example.com"
        # Patch constants in generate_rss_feed
        generate_rss_feed.SITE_NAME = self.site_name
        generate_rss_feed.BASE_URL = self.base_url

    def test_generate_rss_feed_structure(self):
        """Test RSS feed XML structure"""
        now = datetime.now(timezone.utc).isoformat()
        events = [
            {
                'createdAt': now,
                'title': 'Test Event',
                'date': '2026-02-15',
                'url': 'https://example.com/event',
                'guid': 'event1'
            }
        ]
        
        rss_xml = generate_rss_feed.generate_rss_feed(events, max_items=10)
        
        self.assertIn('<?xml version=\'1.0\' encoding=\'utf-8\'?>', rss_xml)
        self.assertIn('<rss version="2.0"', rss_xml)
        self.assertIn(f'<title>{self.site_name} - New Events</title>', rss_xml)
        self.assertIn(f'<link>{self.base_url}</link>', rss_xml)
        self.assertIn('<item>', rss_xml)
        self.assertIn('<title>Test Event (February 15, 2026)</title>', rss_xml)
        self.assertIn('<link>https://example.com/event</link>', rss_xml)
        self.assertIn('<guid isPermaLink="false">event1</guid>', rss_xml)

    def test_generate_rss_feed_respects_max_items(self):
        """Test that RSS feed respects max_items limit"""
        now = datetime.now(timezone.utc).isoformat()
        events = [
            {
                'createdAt': now,
                'title': f'Event {i}',
                'date': '2026-02-15',
                'url': f'https://example.com/event{i}',
                'guid': f'event{i}'
            }
            for i in range(20)
        ]
        
        rss_xml = generate_rss_feed.generate_rss_feed(events, max_items=5)
        
        # Count items
        self.assertEqual(rss_xml.count('<item>'), 5)

if __name__ == '__main__':
    unittest.main()