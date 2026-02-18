#!/usr/bin/env python3
"""Tests for check_microblog_config.py"""

import unittest
import os
import sys
from unittest.mock import patch
from io import StringIO

# Import the module to test
import check_microblog_config


class TestMicroblogConfig(unittest.TestCase):
    """Test cases for micro.blog configuration validation."""

    def setUp(self):
        """Save and clear environment variables before each test."""
        self.saved_destination = os.environ.get('MICROBLOG_DESTINATION')
        self.saved_token = os.environ.get('MB_TOKEN')
        
        # Clear environment variables
        if 'MICROBLOG_DESTINATION' in os.environ:
            del os.environ['MICROBLOG_DESTINATION']
        if 'MB_TOKEN' in os.environ:
            del os.environ['MB_TOKEN']

    def tearDown(self):
        """Restore environment variables after each test."""
        if self.saved_destination is not None:
            os.environ['MICROBLOG_DESTINATION'] = self.saved_destination
        elif 'MICROBLOG_DESTINATION' in os.environ:
            del os.environ['MICROBLOG_DESTINATION']
            
        if self.saved_token is not None:
            os.environ['MB_TOKEN'] = self.saved_token
        elif 'MB_TOKEN' in os.environ:
            del os.environ['MB_TOKEN']

    def test_destination_not_set(self):
        """Test behavior when MICROBLOG_DESTINATION is not set (should use default)."""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            result = check_microblog_config.check_microblog_destination()
            output = fake_out.getvalue()
        
        self.assertEqual(result, 0)  # Changed from 1 to 0 - it's now OK to not set it
        self.assertIn('not set', output)
        self.assertIn('Will use default', output)
        self.assertIn('https://dctechevents.micro.blog/', output)

    def test_destination_correct(self):
        """Test behavior when MICROBLOG_DESTINATION is correct."""
        os.environ['MICROBLOG_DESTINATION'] = 'https://dctechevents.micro.blog/'
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            result = check_microblog_config.check_microblog_destination()
            output = fake_out.getvalue()
        
        self.assertEqual(result, 0)
        self.assertIn('correctly configured', output)

    def test_destination_wrong_blog(self):
        """Test behavior when MICROBLOG_DESTINATION points to wrong blog."""
        os.environ['MICROBLOG_DESTINATION'] = 'https://ross.karchner.com/'
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            result = check_microblog_config.check_microblog_destination()
            output = fake_out.getvalue()
        
        self.assertEqual(result, 1)
        self.assertIn('wrong blog', output)
        self.assertIn('ross.karchner.com', output)

    def test_destination_wrong_blog_no_trailing_slash(self):
        """Test behavior with wrong blog and no trailing slash."""
        os.environ['MICROBLOG_DESTINATION'] = 'https://ross.karchner.com'
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            result = check_microblog_config.check_microblog_destination()
            output = fake_out.getvalue()
        
        self.assertEqual(result, 1)
        self.assertIn('wrong blog', output)

    def test_destination_unexpected_value(self):
        """Test behavior with unexpected destination value."""
        os.environ['MICROBLOG_DESTINATION'] = 'https://example.com/'
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            result = check_microblog_config.check_microblog_destination()
            output = fake_out.getvalue()
        
        self.assertEqual(result, 1)
        self.assertIn('unexpected value', output)

    def test_destination_with_trailing_slash(self):
        """Test that destination with trailing slash is rejected."""
        os.environ['MICROBLOG_DESTINATION'] = 'https://updates.dctech.events/'
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            result = check_microblog_config.check_microblog_destination()
            output = fake_out.getvalue()
        
        self.assertEqual(result, 1)
        self.assertIn('wrong blog', output)

    def test_token_not_set(self):
        """Test behavior when MB_TOKEN is not set."""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            result = check_microblog_config.check_mb_token()
            output = fake_out.getvalue()
        
        self.assertEqual(result, 1)
        self.assertIn('not set', output)

    def test_token_set(self):
        """Test behavior when MB_TOKEN is set correctly."""
        os.environ['MB_TOKEN'] = 'this-is-a-valid-token-with-enough-characters'
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            result = check_microblog_config.check_mb_token()
            output = fake_out.getvalue()
        
        self.assertEqual(result, 0)
        self.assertIn('MB_TOKEN is set', output)

    def test_token_too_short(self):
        """Test behavior when MB_TOKEN is suspiciously short."""
        os.environ['MB_TOKEN'] = 'short'
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            result = check_microblog_config.check_mb_token()
            output = fake_out.getvalue()
        
        self.assertEqual(result, 1)
        self.assertIn('too short', output)

    def test_main_all_correct(self):
        """Test main function with all configuration correct."""
        os.environ['MICROBLOG_DESTINATION'] = 'https://dctechevents.micro.blog/'
        os.environ['MB_TOKEN'] = 'this-is-a-valid-token-with-enough-characters'
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            result = check_microblog_config.main()
            output = fake_out.getvalue()
        
        self.assertEqual(result, 0)
        self.assertIn('All micro.blog configuration checks passed', output)

    def test_main_missing_destination(self):
        """Test main function with missing destination (should now pass with default)."""
        os.environ['MB_TOKEN'] = 'this-is-a-valid-token-with-enough-characters'
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            result = check_microblog_config.main()
            output = fake_out.getvalue()
        
        self.assertEqual(result, 0)  # Changed from 1 to 0 - default is now used
        self.assertIn('All micro.blog configuration checks passed', output)

    def test_main_wrong_destination(self):
        """Test main function with wrong destination."""
        os.environ['MICROBLOG_DESTINATION'] = 'https://ross.karchner.com/'
        os.environ['MB_TOKEN'] = 'this-is-a-valid-token-with-enough-characters'
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            result = check_microblog_config.main()
            output = fake_out.getvalue()
        
        self.assertEqual(result, 1)
        self.assertIn('wrong blog', output)


if __name__ == '__main__':
    unittest.main()
