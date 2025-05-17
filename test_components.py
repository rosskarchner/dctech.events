#!/usr/bin/env python3
"""
Simple test script to validate the main components of the application.
This script checks that all the necessary modules can be imported
and basic functionality is working.
"""

import sys
import os

def test_flask_app():
    """Test that the Flask app can be imported and initialized."""
    try:
        # Use relative path instead of absolute path
        sys.path.append('.')
        from app.app import app
        print("✅ Flask app import successful")
        return True
    except Exception as e:
        print(f"❌ Flask app import failed: {e}")
        return False

def test_boto3():
    """Test that boto3 is installed and can be initialized."""
    try:
        import boto3
        # Try to create a simple client to verify boto3 works
        boto3.client('dynamodb', region_name='us-east-1',
                    endpoint_url='http://localhost:8000',
                    aws_access_key_id='local',
                    aws_secret_access_key='local')
        print("✅ boto3 import and client creation successful")
        return True
    except Exception as e:
        print(f"❌ boto3 test failed: {e}")
        return False

def test_lambda_function():
    """Test that the Lambda function can be imported."""
    try:
        # Use relative path instead of absolute path
        sys.path.append('./aggregator-lambda')
        from lambda_function import handler
        print("✅ Lambda handler import successful")
        return True
    except Exception as e:
        print(f"❌ Lambda handler import failed: {e}")
        return False

def test_freeze_script():
    """Test that the freeze script exists and is executable."""
    try:
        # Use relative path instead of absolute path
        freeze_path = './app/freeze.py'
        if os.path.exists(freeze_path):
            if os.access(freeze_path, os.X_OK):
                print("✅ freeze.py exists and is executable")
                return True
            else:
                print("❌ freeze.py exists but is not executable")
                return False
        else:
            print("❌ freeze.py does not exist")
            return False
    except Exception as e:
        print(f"❌ freeze.py check failed: {e}")
        return False

def test_auth_js_files():
    """Test that the auth.js and common.js files contain the environment-aware redirect functions."""
    try:
        # Use relative paths instead of absolute paths
        auth_js_path = './app/static/js/auth.js'
        common_js_path = './app/static/js/common.js'
        
        # Check if auth.js contains the isLocalEnvironment function
        with open(auth_js_path, 'r') as f:
            auth_js_content = f.read()
            if 'function isLocalEnvironment()' in auth_js_content and 'function getLoginRedirectUrl()' in auth_js_content:
                print("✅ auth.js contains environment-aware redirect functions")
            else:
                print("❌ auth.js is missing environment-aware redirect functions")
                return False
        
        # Check if common.js uses the getLoginRedirectUrl function
        with open(common_js_path, 'r') as f:
            common_js_content = f.read()
            if 'getLoginRedirectUrl()' in common_js_content:
                print("✅ common.js uses environment-aware redirect function")
            else:
                print("❌ common.js is not using environment-aware redirect function")
                return False
        
        return True
    except Exception as e:
        print(f"❌ auth.js and common.js check failed: {e}")
        return False

def test_group_suggest_template():
    """Test that the group_suggest_shell.html template uses the api_url variable."""
    try:
        # Use relative path instead of absolute path
        template_path = './app/templates/group_suggest_shell.html'
        
        # Check if the template contains the api_url variable
        with open(template_path, 'r') as f:
            template_content = f.read()
            if 'hx-get="{{ api_url }}/api/groups/suggest-form"' in template_content:
                print("✅ group_suggest_shell.html uses api_url variable correctly")
                return True
            else:
                print("❌ group_suggest_shell.html is not using api_url variable correctly")
                return False
    except Exception as e:
        print(f"❌ group_suggest_shell.html check failed: {e}")
        return False
    
def test_group_export_csv():
    """Test that the group CSV export functionality works."""
    try:
        # Use relative path instead of absolute path
        sys.path.append('.')
        from app.queries import export_groups_to_csv
        
        # Try to call the function (we don't need to check the result, just that it doesn't error)
        export_groups_to_csv()
        print("✅ Group CSV export function works")
        return True
    except Exception as e:
        print(f"❌ Group CSV export test failed: {e}")
        return False

def test_group_form_ical_required():
    """Test that the ical field in GroupForm is required."""
    try:
        # Use relative path instead of absolute path
        sys.path.append('.')
        from app.forms import GroupForm
        from wtforms.validators import DataRequired
        
        # Check if the ical field has the DataRequired validator
        form = GroupForm()
        has_data_required = False
        for validator in form.ical.validators:
            if isinstance(validator, DataRequired):
                has_data_required = True
                break
        
        if has_data_required:
            print("✅ GroupForm ical field is required")
            return True
        else:
            print("❌ GroupForm ical field is not required")
            return False
    except Exception as e:
        print(f"❌ GroupForm ical field test failed: {e}")
        return False

def test_events_manage_template():
    """Test that the events_manage.html template exists and has the required structure."""
    try:
        # Use relative path instead of absolute path
        template_path = './app/templates/events_manage.html'
        
        # Check if the template exists
        if not os.path.exists(template_path):
            print("❌ events_manage.html does not exist")
            return False
        
        # Check if the template contains the required elements
        with open(template_path, 'r') as f:
            template_content = f.read()
            required_elements = [
                'id="events-content"',
                'class="month-navigation"',
                'id="pending-events"',
                'id="approved-events"',
                'class="event-row pending"',
                'class="event-row approved"',
                'from_aggregator'
            ]
            
            for element in required_elements:
                if element not in template_content:
                    print(f"❌ events_manage.html is missing required element: {element}")
                    return False
            
            print("✅ events_manage.html exists and has the required structure")
            return True
    except Exception as e:
        print(f"❌ events_manage.html check failed: {e}")
        return False

def test_admin_events_shell():
    """Test that the admin_events_shell.html template uses the api_url variable."""
    try:
        # Use relative path instead of absolute path
        template_path = './app/templates/admin_events_shell.html'
        
        # Check if the template contains the api_url variable
        with open(template_path, 'r') as f:
            template_content = f.read()
            if 'hx-get="{{ api_url }}/api/events/manage"' in template_content:
                print("✅ admin_events_shell.html uses api_url variable correctly")
                return True
            else:
                print("❌ admin_events_shell.html is not using api_url variable correctly")
                return False
    except Exception as e:
        print(f"❌ admin_events_shell.html check failed: {e}")
        return False

def test_group_approval_status():
    """Test that the group approval status is correctly updated."""
    try:
        # Use relative path instead of absolute path
        sys.path.append('.')
        from app.queries import approve_group, set_group_pending, get_group_by_id
        from unittest.mock import patch, MagicMock
        
        # Mock the DynamoDB table and get_site_slug function
        with patch('app.queries.get_groups_table') as mock_get_table, \
             patch('app.queries.get_site_slug', return_value='test_site'):
            
            # Create a mock table with a mock update_item method
            mock_table = MagicMock()
            mock_get_table.return_value = mock_table
            
            # Test approve_group function
            group_id = 'test_site!test-group-id'
            success, _ = approve_group(group_id)
            
            # Check that update_item was called with the correct parameters
            mock_table.update_item.assert_called_once()
            args, kwargs = mock_table.update_item.call_args
            
            # Check that the key is correct
            assert kwargs['Key']['id'] == group_id
            
            # Check that the update expression includes approval_status
            assert 'approval_status' in kwargs['UpdateExpression']
            
            # Check that the expression attribute values include the correct status
            assert kwargs['ExpressionAttributeValues'][':status'] == 'test_site!APPROVED'
            
            # Reset the mock for the next test
            mock_table.reset_mock()
            
            # Test set_group_pending function
            success, _ = set_group_pending(group_id)
            
            # Check that update_item was called with the correct parameters
            mock_table.update_item.assert_called_once()
            args, kwargs = mock_table.update_item.call_args
            
            # Check that the key is correct
            assert kwargs['Key']['id'] == group_id
            
            # Check that the update expression includes approval_status
            assert 'approval_status' in kwargs['UpdateExpression']
            
            # Check that the expression attribute values include the correct status
            assert kwargs['ExpressionAttributeValues'][':status'] == 'test_site!PENDING'
            
            # Reset the mock for the next test
            mock_table.reset_mock()
            
            # Test with a group ID that already has the site slug prefix
            from app.app import set_group_pending_route, approve_group_route, delete_group_route
            
            # Mock the necessary functions for route testing
            with patch('app.app.set_group_pending', return_value=(True, "Success")) as mock_set_pending, \
                 patch('app.app.get_pending_groups', return_value=([], None)), \
                 patch('app.app.get_approved_groups', return_value=([], None)), \
                 patch('app.app.render_template') as mock_render:
                
                # Test set_group_pending_route with a group ID that already has the site slug prefix
                set_group_pending_route('test_site!test-group-id')
                
                # Check that set_group_pending was called with the correct ID (unchanged)
                mock_set_pending.assert_called_once_with('test_site!test-group-id')
                
                # Reset the mock
                mock_set_pending.reset_mock()
                
                # Test set_group_pending_route with a group ID that doesn't have the site slug prefix
                set_group_pending_route('test-group-id')
                
                # Check that set_group_pending was called with the correct ID (with prefix added)
                mock_set_pending.assert_called_once_with('test_site!test-group-id')
            
        print("✅ Group approval status update functions work correctly")
        return True
    except Exception as e:
        print(f"❌ Group approval status test failed: {e}")
        return False

def test_groups_manage_template_status_check():
    """Test that the groups_manage.html template correctly checks approval status."""
    try:
        # Use relative path instead of absolute path
        template_path = './app/templates/groups_manage.html'
        
        # Check if the template exists
        if not os.path.exists(template_path):
            print("❌ groups_manage.html does not exist")
            return False
        
        # Check if the template contains the correct status checking logic
        with open(template_path, 'r') as f:
            template_content = f.read()
            
            # Check for the correct pending status check
            if "{% if group.approval_status and 'PENDING' in group.approval_status.split('!')[-1] %}" not in template_content:
                print("❌ groups_manage.html is not correctly checking for PENDING status")
                return False
            
            # Check for the correct approved status check
            if "{% if group.approval_status and 'APPROVED' in group.approval_status.split('!')[-1] %}" not in template_content:
                print("❌ groups_manage.html is not correctly checking for APPROVED status")
                return False
            
        print("✅ groups_manage.html correctly checks approval status")
        return True
    except Exception as e:
        print(f"❌ groups_manage.html status check test failed: {e}")
        return False

if __name__ == "__main__":
    print("Running component tests...")
    
    tests = [
        test_flask_app,
        test_boto3,
        test_lambda_function,
        test_freeze_script,
        test_auth_js_files,
        test_group_suggest_template,
        test_group_export_csv,
        test_group_form_ical_required,
        test_events_manage_template,
        test_admin_events_shell,
        test_group_approval_status,
        test_groups_manage_template_status_check
    ]
    
    success = all(test() for test in tests)
    
    if success:
        print("\n✅ All component tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some component tests failed!")
        sys.exit(1)