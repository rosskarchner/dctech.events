#!/usr/bin/env python3
"""
Tests for post_newsletter_to_microblog.py Micropub formatting.
"""
import pytest
from unittest.mock import Mock, patch
import post_newsletter_to_microblog


class TestMicropubFormat:
    """Tests for Micropub JSON format"""
    
    @patch('post_newsletter_to_microblog.requests.post')
    def test_post_to_microblog_json_format(self, mock_post):
        """Test that content is posted with correct Micropub JSON format"""
        mock_response = Mock()
        mock_response.headers = {'Location': 'https://micro.blog/posts/123'}
        mock_post.return_value = mock_response
        
        result = post_newsletter_to_microblog.post_to_microblog(
            title='Test Newsletter',
            content='<p>Test HTML Content</p>',
            token='fake-token',
            dry_run=False
        )
        
        assert result is True
        assert mock_post.called
        
        # Check the JSON payload structure
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        
        # Verify Microformats 2 JSON structure
        assert payload['type'] == ['h-entry']
        assert 'properties' in payload
        
        # Verify properties are arrays
        assert isinstance(payload['properties']['name'], list)
        assert isinstance(payload['properties']['content'], list)
        
        # Verify content is an object with 'html' key for HTML content
        assert payload['properties']['name'] == ['Test Newsletter']
        content_value = payload['properties']['content'][0]
        assert isinstance(content_value, dict)
        assert 'html' in content_value
        assert content_value['html'] == '<p>Test HTML Content</p>'
    
    @patch('post_newsletter_to_microblog.requests.post')
    def test_post_to_microblog_with_destination(self, mock_post):
        """Test posting with mp-destination parameter"""
        mock_response = Mock()
        mock_response.headers = {'Location': 'https://micro.blog/posts/123'}
        mock_post.return_value = mock_response
        
        result = post_newsletter_to_microblog.post_to_microblog(
            title='Test Newsletter',
            content='<p>Test Content</p>',
            token='fake-token',
            destination='https://updates.dctech.events/',
            dry_run=False
        )
        
        assert result is True
        
        # Check mp-destination in payload
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert payload['properties']['mp-destination'] == ['https://updates.dctech.events/']
    
    def test_post_to_microblog_dry_run(self):
        """Test dry run mode doesn't make actual request"""
        result = post_newsletter_to_microblog.post_to_microblog(
            title='Test Newsletter',
            content='<p>Test Content</p>',
            token='fake-token',
            dry_run=True
        )
        
        assert result is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
