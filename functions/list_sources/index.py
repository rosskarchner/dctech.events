import os
import json
import boto3
from datetime import datetime, UTC

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

def generate_source_row(source, is_admin=False):
    """Generate HTML for a single source row"""
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

def generate_sources_list(sources, is_admin=False):
    """Generate HTML for the list of sources"""
    if not sources:
        return """
        <div id="sources-container" class="sources-list">
            <h2>Event Sources</h2>
            <p>No sources found. Add a new source to get started.</p>
        </div>
        """
    
    sources_html = "".join([generate_source_row(source, is_admin) for source in sources])
    return f"""
    <div id="sources-container" class="sources-list">
        <h2>Event Sources</h2>
        {sources_html}
    </div>
    """

def generate_styles():
    """Generate CSS styles for the sources page"""
    return """
    <style>
        .sources-list {
            margin-top: 20px;
        }
        
        .source-item {
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 15px;
            margin-bottom: 15px;
            display: flex;
            justify-content: space-between;
            align-items: start;
        }
        
        .source-details {
            flex-grow: 1;
        }
        
        .source-details h3 {
            margin: 0 0 10px 0;
            color: #333;
        }
        
        .admin-controls {
            display: flex;
            gap: 10px;
            margin-left: 15px;
        }
        
        .btn-edit, .btn-delete {
            padding: 5px 10px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        
        .btn-edit {
            background: #007bff;
            color: white;
        }
        
        .btn-delete {
            background: #dc3545;
            color: white;
        }
        
        .text-muted {
            color: #6c757d;
            font-size: 0.875em;
        }
        
        .loading-spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #007bff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 10px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .htmx-indicator {
            opacity: 0;
            transition: opacity 500ms ease-in;
        }
        .htmx-request .htmx-indicator {
            opacity: 1
        }
        .htmx-request.htmx-indicator {
            opacity: 1
        }
    </style>
    """

def decode_jwt_token(auth_header):
    """Decode JWT token from Authorization header without verification"""
    try:
        if not auth_header or not auth_header.startswith('Bearer '):
            return {}
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        parts = token.split('.')
        if len(parts) != 3:
            return {}
        
        # Decode the payload (middle part)
        payload = parts[1]
        # Add padding if needed
        padding = '=' * (4 - len(payload) % 4)
        import base64
        decoded = base64.urlsafe_b64decode(payload + padding).decode('utf-8')
        return json.loads(decoded)
    except Exception as e:
        print(f"Error decoding JWT token: {e}")
        return {}

def handler(event, context):
    try:
        # Get the Authorization header
        auth_header = event.get('headers', {}).get('Authorization', '')
        
        # Decode the JWT token to get claims
        claims = decode_jwt_token(auth_header)
        
        # Check if user is admin based on scope
        scope = claims.get('scope', '')
        is_admin = 'admin' in scope.lower()
        
        # Debug logging
        print("Auth header present:", bool(auth_header))
        print("Claims:", json.dumps(claims, indent=2))
        print("Scope:", scope)
        print("Is admin:", is_admin)
        
        # Get all sources from DynamoDB
        response = table.scan()
        sources = response.get('Items', [])
        
        # Sort sources by organization name
        sources.sort(key=lambda x: x.get('organization_name', '').lower())
        
        # Generate the HTML response
        html_content = f"""
        {generate_styles()}
        {generate_sources_list(sources, is_admin)}
        """
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Api-Key',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE',
            },
            'body': html_content
        }

    except Exception as e:
        print(f"Error generating sources list: {str(e)}")
        error_html = """
        <div class="error-message">
            <h3>Error</h3>
            <p>There was a problem loading the sources. Please try again later.</p>
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
