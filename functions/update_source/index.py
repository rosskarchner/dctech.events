import os
import json
import boto3
import base64
import urllib.parse
from datetime import datetime, UTC

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

def parse_form_data(body, is_base64_encoded=False):
    """Parse form data from request body, handling base64 encoding if needed"""
    # Decode base64 if needed
    if is_base64_encoded:
        try:
            body = base64.b64decode(body).decode('utf-8')
        except Exception as e:
            print(f"Error decoding base64: {e}")
            return {}
    
    # Handle JSON data
    if body.startswith('{'):
        try:
            return json.loads(body)
        except Exception as e:
            print(f"Error parsing JSON: {e}")
    
    # Handle form data
    try:
        form_data = {}
        # Split by & and parse each key-value pair
        for field in body.split('&'):
            if '=' in field:
                key, value = field.split('=', 1)
                # URL decode the values
                form_data[key] = urllib.parse.unquote_plus(value)
        return form_data
    except Exception as e:
        print(f"Error parsing form data: {e}")
        return {}

def generate_source_html(source, is_admin=False):
    """Generate HTML for a single source"""
    admin_controls = ""
    if is_admin:
        admin_controls = f"""
            <div class="admin-controls">
                <button class="btn-edit" 
                        hx-get="/api/sources/{source['id']}/edit"
                        hx-target="#source-{source['id']}"
                        title="Edit source">
                    Edit
                </button>
                <button class="btn-delete" 
                        hx-delete="/api/sources/{source['id']}"
                        hx-confirm="Are you sure you want to delete this source?"
                        hx-target="#source-{source['id']}"
                        title="Delete source">
                    Delete
                </button>
            </div>
        """
    
    return f"""
    <div id="source-{source['id']}" class="source-item">
        <div class="source-details">
            <h3>{source['organization_name']}</h3>
            <p><strong>Website:</strong> <a href="{source['url']}" target="_blank">{source['url']}</a></p>
            <p><strong>iCal URL:</strong> {source['ical_url']}</p>
            <p class="text-muted">Updated {source.get('updated_at', 'Unknown date')}</p>
        </div>
        {admin_controls}
    </div>
    """

def handler(event, context):
    try:
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
                    'Content-Type': 'text/html' if 'HX-Request' in event.get('headers', {}) else 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({'error': 'Permission denied'}) if 'HX-Request' not in event.get('headers', {}) else """
                <div class="error-message">
                    <h3>Permission Denied</h3>
                    <p>You do not have permission to update sources.</p>
                </div>
                """
            }
        
        # Get source ID from path parameters
        source_id = event.get('pathParameters', {}).get('id')
        if not source_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'text/html' if 'HX-Request' in event.get('headers', {}) else 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({'error': 'Missing source ID'}) if 'HX-Request' not in event.get('headers', {}) else """
                <div class="error-message">
                    <h3>Error</h3>
                    <p>Missing source ID.</p>
                </div>
                """
            }
        
        # Parse the incoming body
        is_base64_encoded = event.get('isBase64Encoded', False)
        body_data = parse_form_data(event.get('body', '{}'), is_base64_encoded)
        
        # Validate required fields
        required_fields = ['organizationName', 'url', 'icalUrl']
        if not all(field in body_data for field in required_fields):
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'text/html' if 'HX-Request' in event.get('headers', {}) else 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({'error': 'Missing required fields'}) if 'HX-Request' not in event.get('headers', {}) else """
                <div class="error-message">
                    <h3>Error</h3>
                    <p>Missing required fields. Need organization name, website URL, and iCal URL.</p>
                </div>
                """
            }
        
        # Get the existing source
        response = table.get_item(Key={'id': source_id})
        source = response.get('Item')
        
        if not source:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'text/html' if 'HX-Request' in event.get('headers', {}) else 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({'error': 'Source not found'}) if 'HX-Request' not in event.get('headers', {}) else f"""
                <div class="error-message">
                    <h3>Not Found</h3>
                    <p>Source with ID {source_id} not found.</p>
                </div>
                """
            }
        
        # Update the source
        updated_source = {
            'id': source_id,
            'organization_name': body_data['organizationName'],
            'url': body_data['url'],
            'ical_url': body_data['icalUrl'],
            'created_at': source.get('created_at'),
            'updated_at': datetime.now(UTC).isoformat()
        }
        
        # Save to DynamoDB
        table.put_item(Item=updated_source)
        
        # Check if this is an HTMX request
        if 'HX-Request' in event.get('headers', {}):
            # Return HTML for HTMX
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'text/html',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': generate_source_html(updated_source, is_admin)
            }
        else:
            # Return JSON for API
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps(updated_source)
            }

    except Exception as e:
        print(f"Error updating source: {str(e)}")
        
        # Check if this is an HTMX request
        if 'HX-Request' in event.get('headers', {}):
            error_html = """
            <div class="error-message">
                <h3>Error</h3>
                <p>There was a problem updating the source. Please try again later.</p>
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
        else:
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({'error': str(e)})
            }
