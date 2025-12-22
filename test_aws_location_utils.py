#!/usr/bin/env python3
"""
Tests for AWS Places API v2 integration in aws_location_utils.py
"""
import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from botocore.exceptions import NoCredentialsError, ClientError
from aws_location_utils import (
    normalize_address_with_aws,
    _normalize_with_aws,
    _normalize_with_aws_suggest,
    _load_location_cache,
    _save_location_cache,
    LOCATION_CACHE_FILE
)


class TestAWSLocationUtils(unittest.TestCase):
    """Tests for AWS Places API v2 address normalization."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for cache files
        self.test_cache_dir = tempfile.mkdtemp()
        self.original_cache_dir = os.environ.get('CACHE_DIR')
        
        # Patch the CACHE_DIR and LOCATION_CACHE_FILE in the module
        self.cache_file_patcher = patch('aws_location_utils.CACHE_DIR', self.test_cache_dir)
        self.cache_file_patcher.start()
        
        # Reset the global cache
        import aws_location_utils
        aws_location_utils._location_cache = None
        
        # Update the cache file path
        self.test_cache_file = os.path.join(self.test_cache_dir, 'locations.json')
        patch('aws_location_utils.LOCATION_CACHE_FILE', self.test_cache_file).start()

    def tearDown(self):
        """Clean up test fixtures."""
        # Remove the temporary directory
        if os.path.exists(self.test_cache_dir):
            shutil.rmtree(self.test_cache_dir)
        
        # Reset the global cache
        import aws_location_utils
        aws_location_utils._location_cache = None
        
        # Stop the patcher
        self.cache_file_patcher.stop()

    def test_normalize_address_returns_input_for_none(self):
        """Test that None input returns None."""
        result = normalize_address_with_aws(None)
        self.assertIsNone(result)

    def test_normalize_address_returns_input_for_empty_string(self):
        """Test that empty string input returns empty string."""
        result = normalize_address_with_aws('')
        self.assertEqual(result, '')

    def test_normalize_address_returns_input_for_non_string(self):
        """Test that non-string input is returned as-is."""
        result = normalize_address_with_aws(123)
        self.assertEqual(result, 123)

    @patch('aws_location_utils._normalize_with_aws')
    @patch('aws_location_utils.boto3.client')
    def test_normalize_with_aws_successful_call(self, mock_boto_client, mock_normalize):
        """Test successful AWS Places API v2 call."""
        # Mock the AWS normalization to return a normalized address
        mock_normalize.return_value = '1600 Pennsylvania Avenue NW, Washington, DC'
        
        # Call the function
        result = normalize_address_with_aws('The White House')
        
        # Verify the result
        self.assertEqual(result, '1600 Pennsylvania Avenue NW, Washington, DC')
        
        # Verify _normalize_with_aws was called
        mock_normalize.assert_called_once()

    @patch('aws_location_utils._normalize_with_aws')
    @patch('aws_location_utils.boto3.client')
    def test_normalize_with_aws_caches_result(self, mock_boto_client, mock_normalize):
        """Test that AWS results are cached."""
        # Mock the AWS normalization
        mock_normalize.return_value = 'Arlington, VA'
        
        # First call
        result1 = normalize_address_with_aws('Arlington VA')
        
        # Reset the mock to track calls
        mock_normalize.reset_mock()
        
        # Second call with same address
        result2 = normalize_address_with_aws('Arlington VA')
        
        # Should be the same result
        self.assertEqual(result1, result2)
        
        # AWS should not be called on second call (uses cache)
        mock_normalize.assert_not_called()

    @patch('aws_location_utils.boto3.client')
    def test_fallback_to_local_when_aws_fails(self, mock_boto_client):
        """Test fallback to local normalization when AWS fails."""
        # Mock AWS to raise an error
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.search_text.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
            'search_text'
        )
        # Mock suggest to also raise an error (complete failure)
        mock_client.suggest.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
            'suggest'
        )
        
        # Call with an address
        result = normalize_address_with_aws('Arlington, VA 22201, USA')
        
        # Should fall back to local normalization
        # Local normalizer removes zip codes and country names
        self.assertEqual(result, 'Arlington, VA')

    @patch('aws_location_utils.boto3.client')
    def test_fallback_when_no_credentials(self, mock_boto_client):
        """Test fallback to local normalization when AWS credentials are not available."""
        # Mock boto3 to raise NoCredentialsError
        mock_boto_client.side_effect = NoCredentialsError()
        
        # Call with an address
        result = normalize_address_with_aws('Arlington, VA 22201, United States')
        
        # Should fall back to local normalization
        self.assertEqual(result, 'Arlington, VA')

    @patch('aws_location_utils.boto3.client')
    def test_fallback_results_not_cached(self, mock_boto_client):
        """Test that fallback results are not cached."""
        # Mock boto3 to raise NoCredentialsError
        mock_boto_client.side_effect = NoCredentialsError()
        
        # Call with an address
        result = normalize_address_with_aws('Test Location, DC')
        
        # Verify result was normalized
        self.assertIsNotNone(result)
        
        # Check that cache file is either empty or doesn't contain the fallback result
        if os.path.exists(self.test_cache_file):
            with open(self.test_cache_file, 'r') as f:
                cache = json.load(f)
                # Cache should be empty since fallback results aren't cached
                self.assertEqual(len(cache), 0)

    @patch('aws_location_utils.boto3.client')
    def test_aws_no_results_falls_back(self, mock_boto_client):
        """Test fallback when AWS returns no results."""
        # Mock AWS to return empty results
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.search_text.return_value = {
            'ResultItems': []
        }
        # Mock suggest to also return empty results (complete failure)
        mock_client.suggest.return_value = {
            'ResultItems': []
        }
        
        # Call with an address
        result = normalize_address_with_aws('Nonexistent Place, VA')
        
        # Should fall back to local normalization
        self.assertEqual(result, 'Nonexistent Place, VA')

    @patch('aws_location_utils.boto3.client')
    def test_handles_aws_client_creation_error(self, mock_boto_client):
        """Test that AWS client creation errors are handled gracefully."""
        # Mock boto3 to raise an error when creating the client
        mock_boto_client.side_effect = Exception("Client creation failed")
        
        # Call with an address
        result = normalize_address_with_aws('Arlington, VA 22201, USA')
        
        # Should fall back to local normalization
        self.assertEqual(result, 'Arlington, VA')

    @patch('aws_location_utils._normalize_with_aws')
    @patch('aws_location_utils._save_location_cache')
    @patch('aws_location_utils.boto3.client')
    def test_cache_persistence(self, mock_boto_client, mock_save_cache, mock_normalize):
        """Test that cache persists across function calls."""
        with patch.dict(os.environ, {'AWS_LOCATION_INDEX_NAME': 'test-index'}):
            # Mock the AWS normalization
            mock_normalize.return_value = 'Test Location, DC'
            
            # First call
            result1 = normalize_address_with_aws('Test Location')
            
            # Verify save was called
            mock_save_cache.assert_called()

    def test_normalize_with_aws_none_input(self):
        """Test _normalize_with_aws with None input."""
        from aws_location_utils import _normalize_with_aws
        mock_client = MagicMock()
        result = _normalize_with_aws(None, mock_client)
        self.assertIsNone(result)

    def test_normalize_with_aws_non_string_input(self):
        """Test _normalize_with_aws with non-string input."""
        from aws_location_utils import _normalize_with_aws
        mock_client = MagicMock()
        result = _normalize_with_aws(123, mock_client)
        self.assertIsNone(result)

    @patch('aws_location_utils.boto3.client')
    def test_handles_resource_not_found_error(self, mock_boto_client):
        """Test that ResourceNotFoundException is handled gracefully."""
        # Mock AWS to raise ResourceNotFoundException
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.search_text.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Resource not found'}},
            'search_text'
        )
        # Mock suggest to also fail
        mock_client.suggest.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Resource not found'}},
            'suggest'
        )
        
        # Call should not raise an exception
        result = normalize_address_with_aws('Test Address')
        
        # Should fall back to local normalization
        self.assertEqual(result, 'Test Address')

    def test_normalize_with_aws_suggest_successful(self):
        """Test _normalize_with_aws_suggest with successful API call."""
        # Mock AWS client
        mock_client = MagicMock()
        mock_client.suggest.return_value = {
            'ResultItems': [{
                'Address': {
                    'Label': '4100 Fairfax Dr Ste 500, Arlington, VA 22203, United States'
                }
            }]
        }
        
        # Call the suggest function
        result = _normalize_with_aws_suggest('4100 Fairfax Dr ste 500', mock_client)
        
        # Should return normalized address
        self.assertEqual(result, '4100 Fairfax Dr Ste 500, Arlington, VA')
        
    def test_normalize_with_aws_suggest_no_results(self):
        """Test _normalize_with_aws_suggest when API returns no results."""
        # Mock AWS client with empty results
        mock_client = MagicMock()
        mock_client.suggest.return_value = {
            'ResultItems': []
        }
        
        # Call should return None
        result = _normalize_with_aws_suggest('Nonexistent Place', mock_client)
        self.assertIsNone(result)
        
    def test_normalize_with_aws_suggest_none_input(self):
        """Test _normalize_with_aws_suggest with None input."""
        mock_client = MagicMock()
        result = _normalize_with_aws_suggest(None, mock_client)
        self.assertIsNone(result)
        
    def test_normalize_with_aws_suggest_non_string_input(self):
        """Test _normalize_with_aws_suggest with non-string input."""
        mock_client = MagicMock()
        result = _normalize_with_aws_suggest(123, mock_client)
        self.assertIsNone(result)

    def test_normalize_with_aws_suggest_client_error(self):
        """Test _normalize_with_aws_suggest handles ClientError."""
        # Mock AWS client to raise ClientError
        mock_client = MagicMock()
        mock_client.suggest.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
            'suggest'
        )
        
        # Should return None instead of raising
        result = _normalize_with_aws_suggest('Test Address', mock_client)
        self.assertIsNone(result)

    def test_normalize_with_aws_fallback_to_suggest(self):
        """Test that _normalize_with_aws falls back to suggest when search_text returns no results."""
        # Mock AWS client
        mock_client = MagicMock()
        
        # search_text returns no results
        mock_client.search_text.return_value = {
            'ResultItems': []
        }
        
        # suggest returns a result
        mock_client.suggest.return_value = {
            'ResultItems': [{
                'Address': {
                    'Label': '4100 Fairfax Dr Ste 500, Arlington, VA 22203, USA'
                }
            }]
        }
        
        # Call _normalize_with_aws
        result = _normalize_with_aws('4100 Fairfax Dr ste 500, 4100 Fairfax Dr ste 500, Arlington, VA', mock_client)
        
        # Should have called both APIs
        mock_client.search_text.assert_called_once()
        mock_client.suggest.assert_called_once()
        
        # Should return the suggest result
        self.assertEqual(result, '4100 Fairfax Dr Ste 500, Arlington, VA')

    def test_normalize_with_aws_search_text_error_fallback_to_suggest(self):
        """Test that _normalize_with_aws falls back to suggest when search_text raises error."""
        # Mock AWS client
        mock_client = MagicMock()
        
        # search_text raises an error
        mock_client.search_text.side_effect = ClientError(
            {'Error': {'Code': 'ServiceError', 'Message': 'Service error'}},
            'search_text'
        )
        
        # suggest returns a result
        mock_client.suggest.return_value = {
            'ResultItems': [{
                'Address': {
                    'Label': 'Test Location, Washington, DC 20001, United States'
                }
            }]
        }
        
        # Call _normalize_with_aws
        result = _normalize_with_aws('Test Location', mock_client)
        
        # Should have tried search_text and then called suggest
        mock_client.search_text.assert_called_once()
        mock_client.suggest.assert_called_once()
        
        # Should return the suggest result
        self.assertEqual(result, 'Test Location, Washington, DC')

    @patch('aws_location_utils.boto3.client')
    def test_end_to_end_with_suggest_fallback(self, mock_boto_client):
        """Test end-to-end normalization with suggest API fallback."""
        # Mock AWS client
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        
        # search_text returns no results
        mock_client.search_text.return_value = {
            'ResultItems': []
        }
        
        # suggest returns a result
        mock_client.suggest.return_value = {
            'ResultItems': [{
                'Address': {
                    'Label': '4100 Fairfax Dr Ste 500, Arlington, VA 22203, USA'
                }
            }]
        }
        
        # Call the high-level function
        result = normalize_address_with_aws('4100 Fairfax Dr ste 500, 4100 Fairfax Dr ste 500, Arlington, VA, Arlington, VA')
        
        # Should return normalized result from suggest API
        self.assertEqual(result, '4100 Fairfax Dr Ste 500, Arlington, VA')

    def test_normalize_with_aws_suggest_handles_no_credentials(self):
        """Test _normalize_with_aws_suggest handles NoCredentialsError."""
        # Mock AWS client to raise NoCredentialsError
        mock_client = MagicMock()
        mock_client.suggest.side_effect = NoCredentialsError()
        
        # Should return None instead of raising
        result = _normalize_with_aws_suggest('Test Address', mock_client)
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
