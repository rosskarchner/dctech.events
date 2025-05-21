#!/usr/bin/env python3
import unittest
import os
import yaml
import responses
from add_meetup import validate_meetup_url, get_group_name_from_url, create_group_file, get_group_name_from_jsonld

class TestAddMeetup(unittest.TestCase):
    def setUp(self):
        # Create _groups directory if it doesn't exist
        os.makedirs('_groups', exist_ok=True)

    def test_validate_meetup_url_valid(self):
        """Test that valid meetup URLs are accepted."""
        valid_urls = [
            'https://www.meetup.com/dc-python-users-group/',
            'http://www.meetup.com/dc-python-users-group',
            'https://meetup.com/dc-python-users-group/'
        ]
        for url in valid_urls:
            self.assertTrue(validate_meetup_url(url))

    def test_validate_meetup_url_invalid(self):
        """Test that invalid URLs are rejected."""
        invalid_urls = [
            'https://example.com/group',
            'https://meetup.com/',
            'not-a-url',
            'https://www.meetup.com'
        ]
        for url in invalid_urls:
            with self.assertRaises(ValueError):
                validate_meetup_url(url)

    def test_get_group_name_from_url(self):
        """Test that group names are correctly extracted from URLs."""
        test_cases = [
            ('https://www.meetup.com/dc-python-users-group/', 'dc-python-users-group'),
            ('https://www.meetup.com/dc-python-users-group', 'dc-python-users-group'),
            ('http://meetup.com/test-group/', 'test-group'),
            ('https://www.meetup.com/novaopensourcecloud/', 'novaopensourcecloud'),
            ('https://www.meetup.com/dc-aws-users/', 'dc-aws-users')
        ]
        for url, expected in test_cases:
            self.assertEqual(get_group_name_from_url(url), expected)

    @responses.activate
    def test_get_group_name_from_jsonld(self):
        """Test extracting group name from JSON-LD data."""
        test_url = 'https://www.meetup.com/test-group/events/123/'
        test_html = """
        <html>
        <script type="application/ld+json">
        {
            "@context": "http://schema.org",
            "@type": "Event",
            "name": "Test Event",
            "organizer": {
                "@type": "Organization",
                "name": "Test Group Organization"
            }
        }
        </script>
        </html>
        """
        responses.add(responses.GET, test_url, body=test_html, status=200)
        
        # Test successful extraction
        self.assertEqual(get_group_name_from_jsonld(test_url), "Test Group Organization")
        
        # Test missing organization
        responses.reset()
        responses.add(responses.GET, test_url, body='<html></html>', status=200)
        with self.assertRaises(ValueError):
            get_group_name_from_jsonld(test_url)
        
        # Test network error
        responses.reset()
        responses.add(responses.GET, test_url, status=404)
        with self.assertRaises(ValueError):
            get_group_name_from_jsonld(test_url)

    @responses.activate
    def test_create_group_file(self):
        """Test that group files are created correctly."""
        test_cases = [
            ('https://www.meetup.com/test-group/', 'Test Group Organization', 'https://www.meetup.com/test-group'),
            ('https://www.meetup.com/dc-aws-users/', 'DC AWS Users Group', 'https://www.meetup.com/dc-aws-users'),
            ('https://www.meetup.com/novaopensourcecloud/', 'Nova Open Source Cloud', 'https://www.meetup.com/novaopensourcecloud')
        ]

        for test_url, expected_name, expected_clean_url in test_cases:
            test_file = f'_groups/{get_group_name_from_url(test_url)}.yaml'
            
            # Add mock response with JSON-LD data
            test_html = f"""
            <html>
            <script type="application/ld+json">
            {{
                "@context": "http://schema.org",
                "@type": "Event",
                "name": "Test Event",
                "organizer": {{
                    "@type": "Organization",
                    "name": "{expected_name}"
                }}
            }}
            </script>
            </html>
            """
            responses.add(responses.GET, test_url, body=test_html, status=200)

            try:
                # Remove test file if it exists
                if os.path.exists(test_file):
                    os.remove(test_file)

                # Create group file
                create_group_file(test_url)

                # Verify file was created
                self.assertTrue(os.path.exists(test_file))

                # Verify file contents
                with open(test_file, 'r') as f:
                    data = yaml.safe_load(f)
                    self.assertEqual(data['name'], expected_name)
                    self.assertEqual(data['website'], expected_clean_url)
                    self.assertEqual(data['rss'], expected_clean_url + '/events/rss')
                    self.assertTrue(data['active'])

            finally:
                # Cleanup
                if os.path.exists(test_file):
                    os.remove(test_file)
                responses.reset()

    def test_create_group_file_existing(self):
        """Test that creating a group file fails if it already exists."""
        test_url = 'https://www.meetup.com/test-group/'
        test_file = '_groups/test-group.yaml'

        try:
            # Create initial file
            create_group_file(test_url)

            # Try to create it again
            with self.assertRaises(SystemExit):
                create_group_file(test_url)

        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)

if __name__ == '__main__':
    unittest.main()