#!/usr/bin/env python3
"""
Test script to validate the groups management functionality.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add app directory to path
sys.path.append('.')

class TestGroupsManagement(unittest.TestCase):
    """Test the groups management functionality."""
    
    def test_get_approved_groups_pagination(self):
        """Test that get_approved_groups supports pagination."""
        from app.queries import get_approved_groups
        
        # Check that the function accepts pagination parameters
        try:
            result = get_approved_groups(last_evaluated_key=None, limit=50)
            # Function should return a tuple of (groups, last_evaluated_key)
            self.assertTrue(isinstance(result, tuple))
            self.assertEqual(len(result), 2)
            print("✅ get_approved_groups supports pagination")
        except TypeError:
            self.fail("get_approved_groups does not support pagination parameters")
    
    def test_get_pending_groups_pagination(self):
        """Test that get_pending_groups supports pagination."""
        from app.queries import get_pending_groups
        
        # Check that the function accepts pagination parameters
        try:
            result = get_pending_groups(last_evaluated_key=None, limit=50)
            # Function should return a tuple of (groups, last_evaluated_key)
            self.assertTrue(isinstance(result, tuple))
            self.assertEqual(len(result), 2)
            print("✅ get_pending_groups supports pagination")
        except TypeError:
            self.fail("get_pending_groups does not support pagination parameters")
    
    def test_groups_manage_api_url(self):
        """Test that the groups_manage_shell function uses the correct API URL."""
        from app.app import groups_manage_shell
        
        # Mock the environment and render_template function
        with patch('app.app.os.environ.get', return_value='local'), \
             patch('app.app.render_template') as mock_render:
            
            # Call the function
            groups_manage_shell()
            
            # Check that render_template was called with the correct API URL
            mock_render.assert_called_once()
            args, kwargs = mock_render.call_args
            self.assertEqual(kwargs['api_url'], 'http://localhost:5000')
            print("✅ groups_manage_shell uses correct API URL for local environment")
    
    def test_groups_manage_function(self):
        """Test that the groups_manage function uses the separate queries for PENDING and APPROVED groups."""
        from app.app import groups_manage
        
        # Mock the request, get_pending_groups, and get_approved_groups functions
        with patch('app.app.request') as mock_request, \
             patch('app.app.get_pending_groups', return_value=([], None)) as mock_pending, \
             patch('app.app.get_approved_groups', return_value=([], None)) as mock_approved, \
             patch('app.app.render_template') as mock_render:
            
            # Set up the mock request
            mock_request.args.get.return_value = None
            
            # Call the function
            groups_manage()
            
            # Check that both query functions were called
            mock_pending.assert_called_once()
            mock_approved.assert_called_once()
            print("✅ groups_manage uses separate queries for PENDING and APPROVED groups")

if __name__ == "__main__":
    print("Running groups management tests...")
    unittest.main(argv=['first-arg-is-ignored'], exit=False)