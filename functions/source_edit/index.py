import os
import json
import boto3
from datetime import datetime, UTC

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

def generate_edit_form(source):
    """Generate HTML for editing a source"""
    return f"""
    <div id="source-{source['id']}" class="source-item edit-mode">
        <form hx-put="/api/sources/{source['id']}" 
              hx-target="#source-{source['id']}" 
              hx-swap="outerHTML"
              hx-encoding="application/json">
            <div class="form-group">
                <label for="organizationName-{source['id']}">Organization Name:</label>
                <input type="text" 
                       id="organizationName-{source['id']}" 
                       name="organizationName" 
                       value="{source['organization_name']}" 
                       required>
            </div>
            
            <div class="form-group">
                <label for="url-{source['id']}">Website URL:</label>
                <input type="url" 
                       id="url-{source['id']}" 
                       name="url" 
                       value="{source['url']}" 
                       required>
            </div>
            
            <div class="form-group">
                <label for="icalUrl-{source['id']}">iCal URL:</label>
                <input type="url" 
                       id="icalUrl-{source['id']}" 
                       name="icalUrl" 
                       value="{source['ical_url']}" 
                       required>
            </div>
            
            <div class="form-actions">
                <button type="submit" class="btn-save">
                    <span class="htmx-indicator">
                        <div class="loading-spinner"></div> Saving...
                    </span>
                    <span class="submit-text">Save Changes</span>
                </button>
                <button type="button" class="btn-cancel" 
                        hx-get="/api/sources/{source['id']}" 
                        hx-target="#source-{source['id']}" 
                        hx-swap="outerHTML">
                    Cancel
                </button>
            </div>
        </form>
    </div>
    """

def handler(event, context):
    try:
        # Check if this is an HTMX request
        headers = event.get('headers', {}) or {}
        is_htmx = 'HX-Request' in headers or 'hx-request' in headers
        
        # Get the JWT claims from the authorizer context
        auth_context = event.get('requestContext', {}).get('authorizer', {})
        claims = auth_context.get('jwt', {}).get('claims', {})
        
        # Check if user is admin
        scope = claims.get('scope', '')
        is_admin = scope.endswith("admin")
        
        if not is_admin:
            return {
                'statusCode': 403,
                'headers': {
                    'Content-Type': 'text/html',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': """
                <div class="error-message">
                    <h3>Permission Denied</h3>
                    <p>You do not have permission to edit sources.</p>
                </div>
                """
            }
        
        # Get source ID from path parameters
        source_id = event.get('pathParameters', {}).get('id')
        if not source_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'text/html',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': """
                <div class="error-message">
                    <h3>Error</h3>
                    <p>Missing source ID.</p>
                </div>
                """
            }
        
        # Get the source from DynamoDB
        response = table.get_item(Key={'id': source_id})
        source = response.get('Item')
        
        if not source:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'text/html',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': f"""
                <div class="error-message">
                    <h3>Not Found</h3>
                    <p>Source with ID {source_id} not found.</p>
                </div>
                """
            }
        
        # Generate the edit form HTML
        html_content = generate_edit_form(source)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Api-Key',
                'Access-Control-Allow-Methods': 'GET,PUT,DELETE',
            },
            'body': html_content
        }

    except Exception as e:
        print(f"Error generating edit form: {str(e)}")
        error_html = """
        <div class="error-message">
            <h3>Error</h3>
            <p>There was a problem loading the edit form. Please try again later.</p>
        </div>
        """
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'text/html',
                'Access-Control-Allow-Origin': '*',
            },
            'body': error_html
        }
