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
        # Also test importing the route modules
        from app.events_routes import register_events_routes
        from app.groups_routes import register_groups_routes
        print("✅ Flask app and route modules import successful")
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

def test_events_review_shell():
    """Test that the events_review_shell.html template uses the api_url variable correctly."""
    try:
        # Use relative path instead of absolute path
        template_path = './app/templates/events_review_shell.html'
        
        # Check if the template exists
        if not os.path.exists(template_path):
            print("❌ events_review_shell.html does not exist")
            return False
        
        # Check if the template contains the api_url variable
        with open(template_path, 'r') as f:
            template_content = f.read()
            if 'hx-get="{{ api_url }}/api/events/review"' in template_content:
                print("✅ events_review_shell.html uses api_url variable correctly")
                return True
            else:
                print("❌ events_review_shell.html is not using api_url variable correctly")
                return False
    except Exception as e:
        print(f"❌ events_review_shell.html check failed: {e}")
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
            from app.groups_routes import register_groups_routes
            
            # Create a mock Flask app
            mock_app = MagicMock()
            mock_groups_table = MagicMock()
            
            # Register the routes with the mock app
            register_groups_routes(mock_app, mock_groups_table)
            
            # Mock the necessary functions for route testing
            with patch('app.groups_routes.set_group_pending', return_value=(True, "Success")) as mock_set_pending, \
                 patch('app.groups_routes.get_pending_groups', return_value=([], None)), \
                 patch('app.groups_routes.get_approved_groups', return_value=([], None)), \
                 patch('app.groups_routes.render_template') as mock_render:
                
                # Get the route handler function
                set_group_pending_route = None
                for rule in mock_app.route.call_args_list:
                    if rule[0][0] == '/api/groups/pending/<group_id>':
                        set_group_pending_route = rule[1]['methods']
                        break
                
                # If we found the route handler, test it
                if set_group_pending_route:
                    # Test with a group ID that already has the site slug prefix
                    set_group_pending_route('test_site!test-group-id')
                    
                    # Check that set_group_pending was called with the correct ID (unchanged)
                    mock_set_pending.assert_called_once_with('test_site!test-group-id')
                    
                    # Reset the mock
                    mock_set_pending.reset_mock()
                    
                    # Test with a group ID that doesn't have the site slug prefix
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

def test_month_view_route():
    """Test that the month view route works correctly."""
    try:
        # Use relative path instead of absolute path
        sys.path.append('.')
        from app.app import month_view
        from unittest.mock import patch, MagicMock
        
        # Mock the get_events function
        with patch('app.app.get_events', return_value=[]) as mock_get_events, \
             patch('app.app.render_template') as mock_render:
            
            # Test the month_view function
            month_view(2025, 6)
            
            # Check that get_events was called with the correct parameters
            mock_get_events.assert_called_once()
            args, kwargs = mock_get_events.call_args
            
            # Check that the start_date is correct (first day of the month)
            assert kwargs['start_date'].year == 2025
            assert kwargs['start_date'].month == 6
            assert kwargs['start_date'].day == 1
            
            # Check that additional_months is 0
            assert kwargs['additional_months'] == 0
            
            # Check that status is 'APPROVED'
            assert kwargs['status'] == 'APPROVED'
            
            # Check that render_template was called with the correct template
            mock_render.assert_called_once()
            args, kwargs = mock_render.call_args
            assert args[0] == 'month_page.html'
            
            # Check that the template variables are correct
            assert kwargs['year'] == 2025
            assert kwargs['month'] == 6
            assert kwargs['month_name'] == 'June'
            assert kwargs['prev_month'] == 5
            assert kwargs['prev_year'] == 2025
            assert kwargs['next_month'] == 7
            assert kwargs['next_year'] == 2025
            
        print("✅ Month view route works correctly")
        return True
    except Exception as e:
        print(f"❌ Month view route test failed: {e}")
        return False

def test_event_status_namespacing():
    """Test that event status is correctly namespaced with the site slug."""
    try:
        # Use relative path instead of absolute path
        sys.path.append('.')
        from app.events_routes import save_event_to_db, approve_event
        from unittest.mock import patch, MagicMock
        
        # Mock the necessary functions and objects
        with patch('app.events_routes.os.environ.get', return_value='http://localhost:5000'), \
             patch('app.events_routes.events_table') as mock_events_table, \
             patch('app.events_routes.datetime') as mock_datetime, \
             patch('app.events_routes.uuid.uuid4', return_value='test-uuid'), \
             patch('app.events_routes.hashlib.sha256') as mock_hashlib:
            
            # Mock the datetime.now() method
            mock_now = MagicMock()
            mock_now.isoformat.return_value = '2023-01-01T00:00:00'
            mock_datetime.now.return_value = mock_now
            
            # Mock the datetime.strptime method
            mock_datetime.strptime.return_value = mock_now
            
            # Mock the hashlib.sha256().hexdigest() method
            mock_hash = MagicMock()
            mock_hash.hexdigest.return_value = 'test-hash'
            mock_hashlib.return_value = mock_hash
            
            # Test save_event_to_db function
            event_data = {
                'title': 'Test Event',
                'event_date': '2023-01-01',
                'event_time': '12:00 PM',
                'location': 'Test Location',
                'url': 'https://example.com'
            }
            
            success, _ = save_event_to_db(event_data)
            
            # Check that put_item was called with the correct parameters
            mock_events_table.put_item.assert_called_once()
            args, kwargs = mock_events_table.put_item.call_args
            
            # Check that the status is correctly namespaced
            assert kwargs['Item']['status'] == 'localhost_5000!PENDING'
            
            # Reset the mock for the next test
            mock_events_table.reset_mock()
            
            # Test approve_event function
            approve_event('test-id', 'test-month', 'test-sort')
            
            # Check that update_item was called with the correct parameters
            mock_events_table.update_item.assert_called_once()
            args, kwargs = mock_events_table.update_item.call_args
            
            # Check that the status is correctly namespaced
            assert kwargs['ExpressionAttributeValues'][':status'] == 'localhost_5000!APPROVED'
            
        print("✅ Event status is correctly namespaced with the site slug")
        return True
    except Exception as e:
        print(f"❌ Event status namespacing test failed: {e}")
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
        test_events_review_shell,
        test_group_approval_status,
        test_groups_manage_template_status_check,
        test_month_view_route,
        test_event_status_namespacing
    ]
    
    success = all(test() for test in tests)
    
    if success:
        print("\n✅ All component tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some component tests failed!")
        sys.exit(1)