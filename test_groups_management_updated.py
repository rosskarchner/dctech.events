#!/usr/bin/env python3
"""
Test script to validate the updated groups management functionality.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add app directory to path
sys.path.append('.')

class TestGroupsManagementUpdated(unittest.TestCase):
    """Test the updated groups management functionality."""
    
    def test_get_approved_groups_auto_pagination(self):
        """Test that get_approved_groups automatically handles pagination."""
        from app.queries import get_approved_groups
        
        # Mock the DynamoDB scan function to simulate pagination
        with patch('app.queries.get_groups_table') as mock_get_table, \
             patch('app.queries.get_site_slug', return_value='localhost_5000'):
            
            # Create a mock table with a mock scan method
            mock_table = MagicMock()
            mock_get_table.return_value = mock_table
            
            # Set up the scan method to return different responses on each call
            mock_table.scan.side_effect = [
                {
                    'Items': [{'name': 'Group 1', 'id': 'group1'}],
                    'LastEvaluatedKey': {'id': 'group1'}
                },
                {
                    'Items': [{'name': 'Group 2', 'id': 'group2'}],
                    'LastEvaluatedKey': None
                }
            ]
            
            # Call the function
            groups, last_key = get_approved_groups(limit=50)
            
            # Check that scan was called twice (to get all results)
            self.assertEqual(mock_table.scan.call_count, 2)
            
            # Check that we got both groups
            self.assertEqual(len(groups), 2)
            
            # Check that the last_key is None (indicating all results were fetched)
            self.assertIsNone(last_key)
            
            print("✅ get_approved_groups automatically handles pagination")
    
    def test_get_pending_groups_auto_pagination(self):
        """Test that get_pending_groups automatically handles pagination."""
        from app.queries import get_pending_groups
        
        # Mock the DynamoDB scan function to simulate pagination
        with patch('app.queries.get_groups_table') as mock_get_table, \
             patch('app.queries.get_site_slug', return_value='localhost_5000'):
            
            # Create a mock table with a mock scan method
            mock_table = MagicMock()
            mock_get_table.return_value = mock_table
            
            # Set up the scan method to return different responses on each call
            mock_table.scan.side_effect = [
                {
                    'Items': [{'name': 'Group 1', 'id': 'group1'}],
                    'LastEvaluatedKey': {'id': 'group1'}
                },
                {
                    'Items': [{'name': 'Group 2', 'id': 'group2'}],
                    'LastEvaluatedKey': None
                }
            ]
            
            # Call the function
            groups, last_key = get_pending_groups(limit=50)
            
            # Check that scan was called twice (to get all results)
            self.assertEqual(mock_table.scan.call_count, 2)
            
            # Check that we got both groups
            self.assertEqual(len(groups), 2)
            
            # Check that the last_key is None (indicating all results were fetched)
            self.assertIsNone(last_key)
            
            print("✅ get_pending_groups automatically handles pagination")
    
    def test_approve_group_route_handles_fragment(self):
        """Test that the approve_group_route function handles group IDs with # characters."""
        from app.app import approve_group_route
        
        # Mock the necessary functions
        with patch('app.app.get_site_slug', return_value='localhost_5000'), \
             patch('app.app.approve_group', return_value=(True, "Success")) as mock_approve, \
             patch('app.app.get_pending_groups', return_value=([], None)), \
             patch('app.app.get_approved_groups', return_value=([], None)), \
             patch('app.app.render_template') as mock_render:
            
            # Call the function with a group ID containing a !
            approve_group_route('localhost_5000!test-id')
            
            # Check that approve_group was called with the correct ID
            mock_approve.assert_called_once_with('localhost_5000!test-id')
            print("✅ approve_group_route handles group IDs with ! characters")
    
    def test_groups_manage_template_separation(self):
        """Test that the groups_manage.html template separates pending and approved groups."""
        template_path = './app/templates/groups_manage.html'
        
        # Check if the template exists
        self.assertTrue(os.path.exists(template_path), "groups_manage.html does not exist")
        
        # Check if the template contains the required elements for separation
        with open(template_path, 'r') as f:
            template_content = f.read()
            required_elements = [
                'Pending Groups',
                'Approved Groups',
                'id="pending-groups-list"',
                'id="approved-groups-list"',
                'set pending_groups = []',
                'set approved_groups = []'
            ]
            
            for element in required_elements:
                self.assertIn(element, template_content, f"groups_manage.html is missing required element: {element}")
            
            print("✅ groups_manage.html separates pending and approved groups")
    
    def test_group_status_route_id_handling(self):
        """Test that the group status route functions handle group IDs correctly."""
        from app.app import set_group_pending_route, approve_group_route, delete_group_route
        
        # Mock the necessary functions
        with patch('app.app.get_site_slug', return_value='localhost_5000'), \
             patch('app.app.set_group_pending', return_value=(True, "Success")) as mock_set_pending, \
             patch('app.app.approve_group', return_value=(True, "Success")) as mock_approve, \
             patch('app.app.delete_group', return_value=(True, "Success")) as mock_delete, \
             patch('app.app.get_pending_groups', return_value=([], None)), \
             patch('app.app.get_approved_groups', return_value=([], None)), \
             patch('app.app.render_template') as mock_render:
            
            # Test with a group ID that already has the site slug prefix
            set_group_pending_route('localhost_5000!test-id')
            mock_set_pending.assert_called_once_with('localhost_5000!test-id')
            mock_set_pending.reset_mock()
            
            # Test with a group ID that doesn't have the site slug prefix
            set_group_pending_route('test-id')
            mock_set_pending.assert_called_once_with('localhost_5000!test-id')
            mock_set_pending.reset_mock()
            
            # Test with a group ID that has a different site slug prefix
            set_group_pending_route('other_site!test-id')
            mock_set_pending.assert_called_once_with('localhost_5000!test-id')
            mock_set_pending.reset_mock()
            
            # Test approve_group_route with different ID formats
            approve_group_route('localhost_5000!test-id')
            mock_approve.assert_called_once_with('localhost_5000!test-id')
            mock_approve.reset_mock()
            
            approve_group_route('test-id')
            mock_approve.assert_called_once_with('localhost_5000!test-id')
            mock_approve.reset_mock()
            
            # Test delete_group_route with different ID formats
            delete_group_route('localhost_5000!test-id')
            mock_delete.assert_called_once_with('localhost_5000!test-id')
            mock_delete.reset_mock()
            
            delete_group_route('test-id')
            mock_delete.assert_called_once_with('localhost_5000!test-id')
            
            print("✅ Group status route functions handle group IDs correctly")

if __name__ == "__main__":
    print("Running updated groups management tests...")
    unittest.main(argv=['first-arg-is-ignored'], exit=False)