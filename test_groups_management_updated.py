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
        """Test that the approve_group_route function handles group IDs with special characters."""
        from app.app import approve_group_route
        
        # Mock the necessary functions
        with patch('app.app.get_site_slug', return_value='localhost_5000'), \
             patch('app.app._process_group_action', return_value=None) as mock_process:
            
            # Call the function with a group ID containing special characters
            approve_group_route('test-id-with-special-chars')
            
            # Check that _process_group_action was called with the correct ID
            # No site slug should be added at this point
            mock_process.assert_called_once_with('test-id-with-special-chars', "APPROVED")
            print("✅ approve_group_route handles group IDs with special characters")
    
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
             patch('app.app._process_group_action') as mock_process:
            
            # Test approve_group_route
            approve_group_route('test-id')
            mock_process.assert_called_once_with('test-id', "APPROVED")
            mock_process.reset_mock()
            
            # Test set_group_pending_route
            set_group_pending_route('test-id')
            mock_process.assert_called_once_with('test-id', "PENDING")
            mock_process.reset_mock()
            
            # Test delete_group_route
            delete_group_route('test-id')
            mock_process.assert_called_once_with('test-id', None)
            
            print("✅ Group status route functions handle group IDs correctly")

    def test_process_group_action_helper(self):
        """Test that the _process_group_action helper function works correctly."""
        from app.app import _process_group_action
        
        # Mock the necessary functions
        with patch('app.app.get_site_slug', return_value='localhost_5000'), \
             patch('app.app.approve_group', return_value=(True, "Success")) as mock_approve, \
             patch('app.app.set_group_pending', return_value=(True, "Success")) as mock_set_pending, \
             patch('app.app.delete_group', return_value=(True, "Success")) as mock_delete, \
             patch('app.app.get_pending_groups', return_value=([], None)), \
             patch('app.app.get_approved_groups', return_value=([], None)), \
             patch('app.app.render_template') as mock_render:
            
            # Test with approval_state="APPROVED"
            _process_group_action('test-id', "APPROVED")
            mock_approve.assert_called_once_with('test-id')
            mock_approve.reset_mock()
            
            # Test with approval_state="PENDING"
            _process_group_action('test-id', "PENDING")
            mock_set_pending.assert_called_once_with('test-id')
            mock_set_pending.reset_mock()
            
            # Test with approval_state=None (delete)
            _process_group_action('test-id', None)
            mock_delete.assert_called_once_with('test-id')
            mock_delete.reset_mock()
            
            # Test with invalid approval_state
            _process_group_action('test-id', "INVALID")
            
            # Check that render_template was called with the correct arguments
            mock_render.assert_called_with(
                'groups_manage.html', 
                groups=[], 
                api_base_url='http://localhost:5000', 
                message="Error: Invalid approval state: INVALID", 
                message_type="error"
            )
            
            print("✅ _process_group_action helper function works correctly")
    
    def test_edit_group_form_id_handling(self):
        """Test that the edit_group_form function handles group IDs correctly."""
        from app.app import edit_group_form
        
        # Mock the necessary functions
        with patch('app.app.get_site_slug', return_value='localhost_5000'), \
             patch('app.app.get_group_by_id', return_value={'name': 'Test Group'}) as mock_get_group, \
             patch('app.app.render_template', return_value='') as mock_render:
            
            # Call the function with a group ID fragment
            edit_group_form('test-id')
            
            # Check that get_group_by_id was called with the full ID
            mock_get_group.assert_called_once_with('localhost_5000!test-id')
            
            print("✅ edit_group_form handles group ID fragments correctly")
    
    def test_edit_group_id_handling(self):
        """Test that the edit_group function handles group IDs correctly."""
        from app.app import edit_group
        
        # Mock the necessary functions
        with patch('app.app.get_site_slug', return_value='localhost_5000'), \
             patch('app.app.get_group_by_id', return_value={'name': 'Test Group'}), \
             patch('app.app.update_group', return_value=(True, "Success")) as mock_update, \
             patch('app.app.request') as mock_request, \
             patch('app.app.get_pending_groups', return_value=([], None)), \
             patch('app.app.get_approved_groups', return_value=([], None)), \
             patch('app.app.render_template', return_value=''):
            
            # Set up the mock request
            mock_request.form.get.return_value = None
            mock_request.form.validate_on_submit = lambda: True
            
            # Call the function with a group ID fragment
            edit_group('test-id')
            
            # Check that update_group was called with the full ID
            mock_update.assert_called_once()
            args, _ = mock_update.call_args
            self.assertEqual(args[0], 'localhost_5000!test-id')
            
            print("✅ edit_group handles group ID fragments correctly")
    
    def test_groups_manage_template_edit_button(self):
        """Test that the groups_manage.html template has edit buttons with correct HTMX attributes."""
        template_path = './app/templates/groups_manage.html'
        
        # Check if the template exists
        self.assertTrue(os.path.exists(template_path), "groups_manage.html does not exist")
        
        # Check if the template contains the required elements for edit buttons
        with open(template_path, 'r') as f:
            template_content = f.read()
            
            # Check for edit buttons with ID splitting
            self.assertIn('hx-get="{{ api_base_url }}/api/groups/edit-form/{{ group.id.split(\'!\')[-1] }}"', 
                         template_content, 
                         "Edit button is not using ID splitting")
            
            # Check that the edit form container uses only the UUID part of the ID
            self.assertIn('id="edit-form-{{ group.id.split(\'!\')[-1] }}"', 
                         template_content, 
                         "Edit form container is not using UUID-only ID")
            
            # Check that the hx-target attribute uses the UUID-only ID
            self.assertIn('hx-target="#edit-form-{{ group.id.split(\'!\')[-1] }}"', 
                         template_content, 
                         "Edit button hx-target is not using UUID-only ID")
            
            print("✅ groups_manage.html has edit buttons with correct HTMX attributes")

    def test_group_edit_form_template(self):
        """Test that the group_edit_form.html template uses UUID-only IDs."""
        template_path = './app/templates/group_edit_form.html'
        
        # Check if the template exists
        self.assertTrue(os.path.exists(template_path), "group_edit_form.html does not exist")
        
        # Check if the template contains the required elements
        with open(template_path, 'r') as f:
            template_content = f.read()
            
            # Check that the form container uses only the UUID part of the ID
            self.assertIn('id="edit-form-{{ group.id.split(\'!\')[-1] }}"', 
                         template_content, 
                         "Edit form container is not using UUID-only ID")
            
            print("✅ group_edit_form.html uses UUID-only IDs")

if __name__ == "__main__":
    print("Running updated groups management tests...")
    unittest.main(argv=['first-arg-is-ignored'], exit=False)