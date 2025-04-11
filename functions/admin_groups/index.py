import json
import os
import boto3
from boto3.dynamodb.conditions import Key, Attr
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')

def handler(event, context):
    """
    Returns HTML for the admin groups page based on user permissions.
    Checks if the user is in the admin group and returns appropriate content.
    """
    try:
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
        
        # Get the path parameter to determine which groups to fetch
        path = event.get('path', '')
        path_parts = path.split('/')
        
        # Determine which groups to fetch based on the path
        if len(path_parts) > 4 and path_parts[4] == 'pending':
            # Get pending groups
            return get_pending_groups(groups_table)
        elif len(path_parts) > 4 and path_parts[4] == 'approved':
            # Get approved groups
            return get_approved_groups(groups_table)
        elif len(path_parts) > 4 and path_parts[4] == 'all':
            # Get both pending and approved groups
            return get_all_groups(groups_table)
        else:
            # For the base path, return the all groups content directly
            return get_all_groups(groups_table)
    
    except Exception as e:
        logger.error(f"Error in admin_groups handler: {str(e)}")
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

def get_all_groups(groups_table):
    """
    Fetches both pending and approved groups and returns HTML for the complete admin interface.
    """
    try:
        # Query the groups table for pending groups
        pending_response = groups_table.query(
            IndexName='approval-status-index',
            KeyConditionExpression=Key('approval_status').eq('pending')
        )
        
        # Query the groups table for approved groups
        approved_response = groups_table.query(
            IndexName='approval-status-index',
            KeyConditionExpression=Key('approval_status').eq('approved')
        )
        
        pending_groups = pending_response.get('Items', [])
        approved_groups = approved_response.get('Items', [])
        
        # Generate HTML for the admin interface with both group types
        html = """
        <div id="admin-content" class="admin-container">
        """
        
        # Pending groups section
        html += """
            <section class="admin-section">
                <h2>Pending Groups</h2>
        """
        
        if not pending_groups:
            html += """
                <div class="no-groups">
                    <p>No pending groups found.</p>
                </div>
            """
        else:
            for group in pending_groups:
                group_id = group.get('id', '')
                name = group.get('name', 'Unnamed Group')
                website = group.get('website', '#')
                ical = group.get('ical', '#')
                fallback_url = group.get('fallback_url', '')
                
                html += f"""
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
                        <button class="btn btn-approve" 
                                hx-post="https://api.dctech.events/api/admin/groups/{group_id}/approve" 
                                hx-target="#group-{group_id}"
                                hx-swap="outerHTML">
                            Approve
                        </button>
                        <button class="btn btn-delete" 
                                hx-delete="https://api.dctech.events/api/admin/groups/{group_id}" 
                                hx-target="#group-{group_id}"
                                hx-swap="outerHTML">
                            Delete
                        </button>
                    </div>
                </div>
                """
        
        html += """
            </section>
        """
        
        # Approved groups section
        html += """
            <section class="admin-section">
                <h2>Approved Groups</h2>
        """
        
        if not approved_groups:
            html += """
                <div class="no-groups">
                    <p>No approved groups found.</p>
                </div>
            """
        else:
            for group in approved_groups:
                group_id = group.get('id', '')
                name = group.get('name', 'Unnamed Group')
                website = group.get('website', '#')
                ical = group.get('ical', '#')
                fallback_url = group.get('fallback_url', '')
                
                html += f"""
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
                        <button class="btn btn-pause" 
                                hx-post="https://api.dctech.events/api/admin/groups/{group_id}/pause" 
                                hx-target="#group-{group_id}"
                                hx-swap="outerHTML">
                            Pause
                        </button>
                        <button class="btn btn-delete" 
                                hx-delete="https://api.dctech.events/api/admin/groups/{group_id}" 
                                hx-target="#group-{group_id}"
                                hx-swap="outerHTML">
                            Delete
                        </button>
                    </div>
                </div>
                """
        
        html += """
            </section>
        </div>
        
        <style>
            .admin-container {
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }
            .admin-section {
                margin-bottom: 40px;
            }
            .group-card {
                background-color: #f9f9f9;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 20px;
                margin-bottom: 20px;
            }
            .group-details {
                margin-bottom: 15px;
            }
            .group-actions {
                display: flex;
                gap: 10px;
            }
            .btn {
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
            }
            .btn-edit {
                background-color: #2196F3;
                color: white;
            }
            .btn-approve {
                background-color: #4CAF50;
                color: white;
            }
            .btn-pause {
                background-color: #FF9800;
                color: white;
            }
            .btn-delete {
                background-color: #F44336;
                color: white;
            }
            .no-groups {
                background-color: #f5f5f5;
                padding: 15px;
                border-radius: 4px;
                text-align: center;
            }
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
        logger.error(f"Error in get_all_groups: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': f"""
            <div class="error-message">
                <h2>Error</h2>
                <p>An error occurred while fetching groups: {str(e)}</p>
            </div>
            """
        }

def get_pending_groups(groups_table):
    """
    Fetches only pending groups and returns HTML for the admin interface.
    """
    # Implementation similar to get_all_groups but only for pending groups
    pass

def get_approved_groups(groups_table):
    """
    Fetches only approved groups and returns HTML for the admin interface.
    """
    # Implementation similar to get_all_groups but only for approved groups
    pass
