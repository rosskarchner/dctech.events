import json
import os
import boto3
from boto3.dynamodb.conditions import Key, Attr
import logging
import uuid
from datetime import datetime
from shared.template_utils import enqueue_static_render

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
# Initialize SQS client
sqs = boto3.client('sqs')

def handler(event, context):
    """
    Handles actions for specific groups: edit, approve, pause, delete.
    """
    try:
        # Log the event for debugging
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Get the JWT claims from the authorizer
        jwt_claims = event['requestContext']['authorizer']['jwt']['claims']
        
        # Check if user is in the admin group
        cognito_groups = jwt_claims.get('cognito:groups', '')
        # If it's a string representation of a list like "[admins]"
        if isinstance(cognito_groups, str) and cognito_groups.startswith('[') and cognito_groups.endswith(']'):
            cognito_groups = cognito_groups[1:-1].split()
            is_admin = 'admins' in cognito_groups
        else:
            is_admin = False

        # If not admin, return permission denied message
        if not is_admin:
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'text/html'
                },
                'body': """
                <div class="permission-denied">
                    <h2>Permission Denied</h2>
                    <p>You do not have permission to manage groups. Please contact an administrator if you believe this is an error.</p>
                </div>
                """
            }
        
        # Get the groups table name from environment variable
        groups_table_name = os.environ.get('GROUPS_TABLE')
        if not groups_table_name:
            raise ValueError("GROUPS_TABLE environment variable is not set")
        
        # Initialize the groups table
        groups_table = dynamodb.Table(groups_table_name)
        
        # Get the group ID from the path parameters
        path_parameters = event.get('pathParameters', {})
        group_id = path_parameters.get('id')
        
        if not group_id:
            raise ValueError("Invalid request: missing group ID")
        
        # Get the path to determine the action
        path = event["requestContext"]["http"]["path"]
        
        # Determine the action based on the HTTP method and path
        http_method = event["requestContext"]["http"]["method"]
        
        if http_method == 'GET' and path.endswith('/edit'):
            # Get the edit form for a group
            return get_edit_form(groups_table, group_id)
        elif http_method == 'GET':
            # Get a specific group
            return get_group(groups_table, group_id)
        elif http_method == 'PUT':
            # Update a group
            return update_group(groups_table, group_id, event)
        elif http_method == 'DELETE':
            # Delete a group
            return delete_group(groups_table, group_id)
        elif http_method == 'POST' and path.endswith('/approve'):
            # Approve a group
            return approve_group(groups_table, group_id)
        elif http_method == 'POST' and path.endswith('/pause'):
            # Pause a group
            return pause_group(groups_table, group_id)
        else:
            # Unknown action
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'text/html'
                },
                'body': """
                <div class="error-message">
                    <h2>Error</h2>
                    <p>Unknown action requested.</p>
                </div>
                """
            }
    
    except Exception as e:
        logger.error(f"Error in admin_group_actions handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': f"""
            <div class="error-message">
                <h2>Error</h2>
                <p>An error occurred while processing your request: {str(e)}</p>
            </div>
            """
        }

def get_edit_form(groups_table, group_id):
    """
    Returns an HTML form for editing a group.
    """
    try:
        # Get the group from the database
        response = groups_table.get_item(
            Key={
                'id': group_id
            }
        )
        
        group = response.get('Item', {})
        if not group:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'text/html'
                },
                'body': """
                <div class="error-message">
                    <h2>Error</h2>
                    <p>Group not found.</p>
                </div>
                """
            }
        
        # Extract group details
        name = group.get('name', '')
        website = group.get('website', '')
        ical = group.get('ical', '')
        fallback_url = group.get('fallback_url', '')
        
        # Generate the edit form HTML
        html = f"""
        <div class="edit-form" id="group-{group_id}">
            <h3>Edit Group: {name}</h3>
            <form hx-put="https://api.dctech.events/api/admin/groups/{group_id}" 
                  hx-target="#group-{group_id}" 
                  hx-swap="outerHTML">
                <div class="form-group">
                    <label for="name">Group Name</label>
                    <input type="text" id="name" name="name" value="{name}" required>
                </div>
                <div class="form-group">
                    <label for="website">Website URL</label>
                    <input type="url" id="website" name="website" value="{website}" required>
                </div>
                <div class="form-group">
                    <label for="ical">iCal URL</label>
                    <input type="url" id="ical" name="ical" value="{ical}" required>
                </div>
                <div class="form-group">
                    <label for="fallback_url">Event Fallback URL <span class="optional">(optional)</span></label>
                    <input type="url" id="fallback_url" name="fallback_url" value="{fallback_url}" placeholder="https://example.com/events">
                    <div class="help-text">By default, we only import events from iCal that have a URL. If you provide a fallback URL, we will use that link for events that don't have a URL. Events without a URL and no fallback URL will be ignored.</div>
                </div>
                <div class="form-actions">
                    <button type="button" class="btn" 
                            hx-get="https://api.dctech.events/api/admin/groups/all" 
                            hx-target="#admin-content" 
                            hx-swap="outerHTML">
                        Cancel
                    </button>
                    <button type="submit" class="btn btn-edit">Save Changes</button>
                </div>
            </form>
        </div>
        
        <style>
            .edit-form {{
                background-color: #f9f9f9;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 20px;
            }}
            .form-group {{
                margin-bottom: 15px;
            }}
            label {{
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
            }}
            .optional {{
                font-weight: normal;
                font-style: italic;
                color: #666;
            }}
            .help-text {{
                font-size: 14px;
                color: #666;
                margin-top: 5px;
            }}
            input[type="text"], input[type="url"] {{
                width: 100%;
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }}
            .form-actions {{
                display: flex;
                justify-content: flex-end;
                gap: 10px;
                margin-top: 20px;
            }}
            .btn {{
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }}
            .btn-edit {{
                background-color: #2196F3;
                color: white;
            }}
        </style>
        """
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': html
        }
    
    except Exception as e:
        logger.error(f"Error getting edit form: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': f"""
            <div class="error-message">
                <p>Error getting edit form: {str(e)}</p>
            </div>
            """
        }

def get_group(groups_table, group_id):
    """
    Returns HTML for a specific group.
    """
    try:
        # Get the group from the database
        response = groups_table.get_item(
            Key={
                'id': group_id
            }
        )
        
        group = response.get('Item', {})
        if not group:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'text/html'
                },
                'body': """
                <div class="error-message">
                    <h2>Error</h2>
                    <p>Group not found.</p>
                </div>
                """
            }
        
        # Extract group details
        name = group.get('name', '')
        website = group.get('website', '')
        ical = group.get('ical', '')
        fallback_url = group.get('fallback_url', '')
        approval_status = group.get('approval_status', 'pending')
        
        # Generate the group HTML
        html = f"""
        <div class="group-card" id="group-{group_id}">
            <h3>{name}</h3>
            <div class="group-details">
                <p><strong>Website:</strong> <a href="{website}" target="_blank">{website}</a></p>
                <p><strong>iCal URL:</strong> <a href="{ical}" target="_blank">{ical}</a></p>
                {f'<p><strong>Event Fallback URL:</strong> <a href="{fallback_url}" target="_blank">{fallback_url}</a></p>' if fallback_url else ''}
                <p><strong>Status:</strong> {approval_status}</p>
            </div>
            <div class="group-actions">
                <button class="btn btn-edit" 
                        hx-get="https://api.dctech.events/api/admin/groups/{group_id}/edit" 
                        hx-target="#group-{group_id}"
                        hx-swap="innerHTML">
                    Edit
                </button>
        """
        
        if approval_status == 'pending':
            html += f"""
                <button class="btn btn-approve" 
                        hx-post="https://api.dctech.events/api/admin/groups/{group_id}/approve" 
                        hx-target="#admin-content"
                        hx-swap="outerHTML"
                        hx-trigger="click"
                        hx-confirm="Are you sure you want to approve this group?">
                    Approve
                </button>
            """
        else:
            html += f"""
                <button class="btn btn-pause" 
                        hx-post="https://api.dctech.events/api/admin/groups/{group_id}/pause" 
                        hx-target="#admin-content"
                        hx-swap="outerHTML"
                        hx-trigger="click"
                        hx-confirm="Are you sure you want to pause this group?">
                    Pause
                </button>
            """
        
        html += f"""
                <button class="btn btn-delete" 
                        hx-delete="https://api.dctech.events/api/admin/groups/{group_id}" 
                        hx-target="#admin-content"
                        hx-swap="outerHTML"
                        hx-trigger="click"
                        hx-confirm="Are you sure you want to delete this group? This action cannot be undone.">
                    Delete
                </button>
            </div>
        </div>
        """
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': html
        }
    
    except Exception as e:
        logger.error(f"Error getting group: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': f"""
            <div class="error-message">
                <p>Error getting group: {str(e)}</p>
            </div>
            """
        }

def update_group(groups_table, group_id, event):
    """
    Updates a group with new information.
    """
    try:
        # Parse the form data from the request body
        body = event.get('body', '')
        
        # Check if the body is base64 encoded
        is_base64_encoded = event.get('isBase64Encoded', False)
        if is_base64_encoded:
            import base64
            body = base64.b64decode(body).decode('utf-8')
        
        # Parse form-encoded data
        form_data = {}
        for pair in body.split('&'):
            if '=' in pair:
                key, value = pair.split('=', 1)
                # URL decode the values
                from urllib.parse import unquote
                form_data[key] = unquote(value)
        
        # Get the group from the database to ensure it exists
        response = groups_table.get_item(
            Key={
                'id': group_id
            }
        )
        
        group = response.get('Item', {})
        if not group:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'text/html'
                },
                'body': """
                <div class="error-message">
                    <h2>Error</h2>
                    <p>Group not found.</p>
                </div>
                """
            }
        
        # Prepare update expression and attribute values
        update_expression = 'SET #name = :name, website = :website, ical = :ical, updated_at = :updated_at'
        expression_attribute_values = {
            ':name': form_data.get('name', group.get('name', '')),
            ':website': form_data.get('website', group.get('website', '')),
            ':ical': form_data.get('ical', group.get('ical', '')),
            ':updated_at': datetime.now().isoformat()
        }
        
        # Add fallback_url if provided
        fallback_url = form_data.get('fallback_url', '').strip()
        if fallback_url:
            update_expression += ', fallback_url = :fallback_url'
            expression_attribute_values[':fallback_url'] = fallback_url
        elif 'fallback_url' in group:
            # Remove fallback_url if it exists in the group but was not provided in the form
            update_expression += ' REMOVE fallback_url'
        
        # Update the group in the database
        groups_table.update_item(
            Key={
                'id': group_id
            },
            UpdateExpression=update_expression,
            ExpressionAttributeNames={
                '#name': 'name'  # 'name' is a reserved word in DynamoDB
            },
            ExpressionAttributeValues=expression_attribute_values
        )
        
        # For updates, return the updated group card
        name = form_data.get('name', group.get('name', ''))
        website = form_data.get('website', group.get('website', ''))
        ical = form_data.get('ical', group.get('ical', ''))
        approval_status = group.get('approval_status', 'pending')
        
        html = f"""
        <div class="group-card" id="group-{group_id}">
            <h3>{name}</h3>
            <div class="group-details">
                <p><strong>Website:</strong> <a href="{website}" target="_blank">{website}</a></p>
                <p><strong>iCal URL:</strong> <a href="{ical}" target="_blank">{ical}</a></p>
                {f'<p><strong>Event Fallback URL:</strong> <a href="{fallback_url}" target="_blank">{fallback_url}</a></p>' if fallback_url else ''}
            </div>
            <div class="group-actions">
                <button class="btn btn-edit" 
                        hx-get="https://api.dctech.events/api/admin/groups/{group_id}/edit" 
                        hx-target="#group-{group_id}"
                        hx-swap="innerHTML">
                    Edit
                </button>
        """
        
        if approval_status == 'pending':
            html += f"""
                <button class="btn btn-approve" 
                        hx-post="https://api.dctech.events/api/admin/groups/{group_id}/approve" 
                        hx-target="#group-{group_id}"
                        hx-swap="outerHTML">
                    Approve
                </button>
            """
        else:
            html += f"""
                <button class="btn btn-pause" 
                        hx-post="https://api.dctech.events/api/admin/groups/{group_id}/pause" 
                        hx-target="#group-{group_id}"
                        hx-swap="outerHTML">
                    Pause
                </button>
            """
        
        html += f"""
                <button class="btn btn-delete" 
                        hx-delete="https://api.dctech.events/api/admin/groups/{group_id}" 
                        hx-target="#group-{group_id}"
                        hx-swap="outerHTML">
                    Delete
                </button>
            </div>
        </div>
        """
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': html
        }
    
    except Exception as e:
        logger.error(f"Error updating group: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': f"""
            <div class="error-message">
                <p>Error updating group: {str(e)}</p>
            </div>
            """
        }

def delete_group(groups_table, group_id):
    """
    Deletes a group from the database.
    """
    try:
        # Get the group name for the success message
        response = groups_table.get_item(
            Key={
                'id': group_id
            }
        )
        
        group = response.get('Item', {})
        group_name = group.get('name', 'Group')
        
        # Delete the group from the database
        groups_table.delete_item(
            Key={
                'id': group_id
            }
        )
        
        # Trigger a render of the groups page
        enqueue_static_render(page='groups/index.mustache')
        
        # Return success message with auto-refresh
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html',
                'HX-Trigger': 'refreshGroupsList'
            },
            'body': f"""
            <div class="success-message" id="group-{group_id}">
                <p>"{group_name}" has been deleted successfully.</p>
            </div>
            """
        }
    
    except Exception as e:
        logger.error(f"Error deleting group: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': f"""
            <div class="error-message">
                <p>Error deleting group: {str(e)}</p>
            </div>
            """
        }

def approve_group(groups_table, group_id):
    """
    Approves a pending group.
    """
    try:
        # Get the group name for the success message
        response = groups_table.get_item(
            Key={
                'id': group_id
            }
        )
        
        group = response.get('Item', {})
        group_name = group.get('name', 'Group')
        
        # Update the group in the database
        groups_table.update_item(
            Key={
                'id': group_id
            },
            UpdateExpression='SET approval_status = :status, updated_at = :updated_at',
            ExpressionAttributeValues={
                ':status': 'approved',
                ':updated_at': datetime.now().isoformat()
            }
        )
        
        # Trigger a render of the groups page
        enqueue_static_render(page='groups/index.html')
        
        # Return success message with auto-refresh
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html',
                'HX-Trigger': 'refreshGroupsList'
            },
            'body': f"""
            <div class="success-message" id="group-{group_id}">
                <p>"{group_name}" has been approved successfully.</p>
            </div>
            """
        }
    
    except Exception as e:
        logger.error(f"Error approving group: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': f"""
            <div class="error-message">
                <p>Error approving group: {str(e)}</p>
            </div>
            """
        }

def pause_group(groups_table, group_id):
    """
    Pauses an approved group.
    """
    try:
        # Get the group name for the success message
        response = groups_table.get_item(
            Key={
                'id': group_id
            }
        )
        
        group = response.get('Item', {})
        group_name = group.get('name', 'Group')
        
        # Update the group in the database
        groups_table.update_item(
            Key={
                'id': group_id
            },
            UpdateExpression='SET approval_status = :status, updated_at = :updated_at',
            ExpressionAttributeValues={
                ':status': 'pending',
                ':updated_at': datetime.now().isoformat()
            }
        )
        
        # Trigger a render of the groups page
        enqueue_static_render(page='groups/index.html')
        
        # Return success message with auto-refresh
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html',
                'HX-Trigger': 'refreshGroupsList'
            },
            'body': f"""
            <div class="success-message" id="group-{group_id}">
                <p>"{group_name}" has been paused successfully.</p>
            </div>
            """
        }
    
    except Exception as e:
        logger.error(f"Error pausing group: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': f"""
            <div class="error-message">
                <p>Error pausing group: {str(e)}</p>
            </div>
            """
        }
