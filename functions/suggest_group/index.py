import boto3
import uuid
import os
from datetime import datetime
import urllib.parse
import base64

def handler(event, context):
    """
    Handles the submission of a group suggestion.
    Expects form-encoded input and returns HTML output.
    Authentication is handled by API Gateway authorizer.
    """
    # Get user information from the JWT claims
    jwt_claims = event['requestContext']['authorizer']['jwt']['claims']
    user_id = jwt_claims.get('sub')
    user_email = jwt_claims.get('email')
    
    try:
        # Parse the form data from the request body
        body = event.get('body', '')
        
        # Check if the body is base64 encoded
        if event.get('isBase64Encoded', False):
            body = base64.b64decode(body).decode('utf-8')
        
        # Parse form data
        form_data = dict(urllib.parse.parse_qsl(body))
        
        # Extract form fields
        name = form_data.get('name', '').strip()
        website = form_data.get('website', '').strip()
        ical = form_data.get('ical', '').strip()
        
        # Validate required fields
        if not name or not website or not ical:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'text/html'
                },
                'body': """
                <div class="error-message">
                    <h3>Error</h3>
                    <p>Name, website, and iCal URL are all required fields.</p>
                    <button onclick="window.history.back()">Go Back</button>
                </div>
                <style>
                    .error-message {
                        background-color: #ffebee;
                        border: 1px solid #ffcdd2;
                        color: #c62828;
                        padding: 20px;
                        border-radius: 4px;
                        margin-top: 20px;
                        text-align: center;
                    }
                    button {
                        background-color: #0066cc;
                        color: white;
                        border: none;
                        padding: 10px 20px;
                        border-radius: 4px;
                        font-size: 16px;
                        cursor: pointer;
                        margin-top: 10px;
                    }
                </style>
                """
            }
        
        # Get the DynamoDB table
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(os.environ.get('GROUPS_TABLE'))
        
        # Create a new group suggestion
        group_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        item = {
            'id': group_id,
            'name': name,
            'website': website,
            'ical': ical,  # iCal is required
            'status': 'pending',  # Pending approval
            'created_at': timestamp,
            'created_by': user_id,
            'created_by_email': user_email
        }
        
        # Save to DynamoDB
        table.put_item(Item=item)
        
        # Return success HTML
        success_html = """
        <div class="success-message">
            <h3>Thank you for your submission!</h3>
            <p>We'll review the group and add it to our listings soon.</p>
            <button hx-get="https://api.dctech.events/api/groups/suggest-form" 
                    hx-target="#group-form" 
                    hx-swap="outerHTML">
                Submit Another Group
            </button>
        </div>
        
        <style>
            .success-message {
                background-color: #e8f5e9;
                border: 1px solid #a5d6a7;
                color: #2e7d32;
                padding: 20px;
                border-radius: 4px;
                margin-top: 20px;
                text-align: center;
            }
            button {
                background-color: #0066cc;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-size: 16px;
                cursor: pointer;
                margin-top: 10px;
            }
            button:hover {
                background-color: #0055aa;
            }
        </style>
        """
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': success_html
        }
        
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': f"""
            <div class="error-message">
                <h3>Error</h3>
                <p>An error occurred processing your request. Please try again later.</p>
                <button onclick="window.history.back()">Go Back</button>
            </div>
            <style>
                .error-message {{
                    background-color: #ffebee;
                    border: 1px solid #ffcdd2;
                    color: #c62828;
                    padding: 20px;
                    border-radius: 4px;
                    margin-top: 20px;
                    text-align: center;
                }}
                button {{
                    background-color: #0066cc;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 4px;
                    font-size: 16px;
                    cursor: pointer;
                    margin-top: 10px;
                }}
            </style>
            """
        }
