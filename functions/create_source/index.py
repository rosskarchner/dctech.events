import os
import json
import boto3
import uuid
import urllib.parse
import base64
from datetime import datetime, UTC

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

def handler(event, context):
    try:
        # Debug logging
        print("Event received:", json.dumps(event, default=str))
        
        # Parse request body
        body = event.get('body', '')
        
        # Check if the body is base64 encoded
        is_base64_encoded = event.get('isBase64Encoded', False)
        if is_base64_encoded and body:
            try:
                body = base64.b64decode(body).decode('utf-8')
                print("Decoded base64 body:", body)
            except Exception as e:
                print(f"Error decoding base64 body: {e}")
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'text/html'},
                    'body': f'<div class="error-message">Invalid base64 encoding: {str(e)}</div>'
                }
        
        print("Request body (after potential decoding):", body)
        
        # Check content type to determine how to parse
        content_type = event.get('headers', {}).get('content-type', '')
        print(f"Content-Type: {content_type}")
        
        # Parse body based on content type
        if 'application/json' in content_type:
            # JSON data
            try:
                body_data = json.loads(body)
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'text/html'},
                    'body': f'<div class="error-message">Invalid JSON: {str(e)}</div>'
                }
        else:
            # Form data
            body_data = {}
            if body:
                form_data = urllib.parse.parse_qs(body)
                # Convert from lists to single values
                for key, value in form_data.items():
                    body_data[key] = value[0] if value else ''
        
        # Extract source details
        organization_name = body_data.get('organizationName', '')
        url = body_data.get('url', '')
        ical_url = body_data.get('icalUrl', '')
        
        print(f"Parsed values: org={organization_name}, url={url}, ical={ical_url}")
        
        # Validate required fields
        if not organization_name or not url or not ical_url:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'text/html',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': '<div class="error-message">Missing required fields</div>'
            }
        
        # Generate unique ID and timestamp
        source_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()
        
        # Create source item
        source = {
            'id': source_id,
            'organization_name': organization_name,
            'url': url,
            'ical_url': ical_url,
            'created_at': timestamp,
            'updated_at': timestamp
        }
        
        # Save to DynamoDB
        table.put_item(Item=source)
        
        # Return success message with HTMX trigger to reload sources list
        success_html = f"""
        <div id="adminFormContainer">
            <div class="success-message">
                <h3>Source Added Successfully</h3>
                <p>The source "{organization_name}" has been added.</p>
                <button class="btn-primary" 
                        hx-get="/api/sources/form" 
                        hx-target="#adminFormContainer" 
                        hx-swap="outerHTML">
                    Add Another Source
                </button>
                <div hx-trigger="load" hx-get="/api/sources" hx-target="#sourcesContainer" hx-swap="innerHTML"></div>
            </div>
        </div>
        """
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Api-Key',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE',
            },
            'body': success_html
        }
        
    except Exception as e:
        print(f"Error creating source: {str(e)}")
        error_html = f"""
        <div id="adminFormContainer">
            <div class="error-message">
                <h3>Error</h3>
                <p>There was a problem creating the source: {str(e)}</p>
                <button class="btn-primary" 
                        hx-get="/api/sources/form" 
                        hx-target="#adminFormContainer" 
                        hx-swap="outerHTML">
                    Try Again
                </button>
            </div>
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
