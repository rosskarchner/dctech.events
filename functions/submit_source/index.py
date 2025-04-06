import os
import json
import boto3
import uuid
import base64
import urllib.parse
from datetime import datetime, timedelta

cognito = boto3.client('cognito-idp')

def handler(event, context):
    try:
        print("Submit source request received")
        print(f"Event: {json.dumps(event, default=str)}")

        # Parse the request body
        body = event.get('body', '{}')
        if event.get('isBase64Encoded', False):
            body = base64.b64decode(body).decode('utf-8')
        
        try:
            source_data = json.loads(body)
        except json.JSONDecodeError:
            # Handle form-encoded data
            source_data = {}
            for field in body.split('&'):
                if '=' in field:
                    key, value = field.split('=', 1)
                    source_data[urllib.parse.unquote(key)] = urllib.parse.unquote(value)
        
        # Validate required fields
        required_fields = ['name', 'ical_url']
        for field in required_fields:
            if field not in source_data or not source_data[field]:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'text/html'},
                    'body': generate_error_html(f'Missing required field: {field}')
                }
        
        auth_context = event["requestContext"]["authorizer"]["lambda"]

        # Create the source item
        source_item = {
            'id': str(uuid.uuid4()),
            'name': source_data['name'],
            'website': source_data.get('website', ''),
            'ical_url': source_data['ical_url'],
            'submitter_id': auth_context["sub"],
            'submitter_name': auth_context.get("custom_nickname", ""),
            'submitter_url': auth_context.get("custom_website", ""),
            'submitter_email': auth_context['email'],
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        # Save to DynamoDB
        table_name = os.environ['TABLE_NAME']
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(table_name)
        
        table.put_item(Item=source_item)
        
        # Return HTML response suitable for HTMX
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html',
                'HX-Trigger': json.dumps({"showMessage": "Source submitted successfully"})
            },
            'body': generate_success_html(source_item['name'])
        }
            
    except Exception as e:
        print(f"Error processing source submission: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'text/html',
                'HX-Trigger': json.dumps({"showError": str(e)})
            },
            'body': generate_error_html(f'Error processing source submission: {str(e)}')
        }

def generate_success_html(source_name):
    """Generate a partial HTML response for successful submission"""
    return f"""
<div class="success-message" id="submission-result">
    <div class="success-icon">✓</div>
    <h2>Thank You!</h2>
    <p>Your event source <strong>{source_name}</strong> has been submitted successfully.</p>
    <p>Our team will review your submission and add it to our event calendar if approved.</p>
    <p>You will receive an email notification when your submission has been reviewed.</p>
    
    <div class="actions">
        <a href="#" class="btn" hx-get="/api/submit-source-form" hx-target="#form-container" hx-swap="innerHTML">Add Another Source</a>
        <a href="/sources" class="btn">View All Sources</a>
        <a href="/" class="btn">Return to Home</a>
    </div>
</div>
"""

def generate_error_html(error_message):
    """Generate a partial HTML response for error"""
    return f"""
<div class="error-message" id="submission-result">
    <div class="error-icon">✗</div>
    <h2>Submission Error</h2>
    <p>We encountered an error while processing your submission:</p>
    <p><strong>{error_message}</strong></p>
    <p>Please try again or contact support if the issue persists.</p>
    
    <div class="actions">
        <button class="btn" hx-get="/api/submit-source-form" hx-target="#form-container" hx-swap="innerHTML">Try Again</button>
    </div>
</div>
"""
