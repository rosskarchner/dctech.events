import os
import json
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

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
            <p class="text-muted">Added {source.get('created_at', 'Unknown date')}</p>
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
        
        # Get the source from DynamoDB
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
        
        # Check if this is an HTMX request
        if 'HX-Request' in event.get('headers', {}):
            # Return HTML for HTMX
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'text/html',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': generate_source_html(source, is_admin)
            }
        else:
            # Return JSON for API
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps(source)
            }

    except Exception as e:
        print(f"Error getting source: {str(e)}")
        
        # Check if this is an HTMX request
        if 'HX-Request' in event.get('headers', {}):
            error_html = """
            <div class="error-message">
                <h3>Error</h3>
                <p>There was a problem loading the source. Please try again later.</p>
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
