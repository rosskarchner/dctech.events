import json
import os
import boto3
import uuid
from datetime import datetime
import urllib.parse
import base64

dynamodb = boto3.resource('dynamodb')
sources_table = dynamodb.Table(os.environ['TABLE_NAME'])
cognito = boto3.client('cognito-idp')

def parse_form_data(body, is_base64_encoded=False):
    """Parse form data from request body"""
    if is_base64_encoded:
        body = base64.b64decode(body).decode('utf-8')
    
    # Parse form data
    form_data = {}
    for field in body.split('&'):
        if '=' in field:
            key, value = field.split('=', 1)
            form_data[urllib.parse.unquote(key)] = urllib.parse.unquote(value)
    
    return form_data

def handler(event, context):
    try:
        print("Submit source request received")
        print(f"Event: {json.dumps(event, default=str)}")
        
        # Get user ID from the request context
        user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']
        print(f"User ID: {user_id}")
        
        # Parse request body - handle both JSON and form-encoded data
        if event.get('isBase64Encoded', False):
            # Handle base64 encoded form data
            form_data = parse_form_data(event['body'], is_base64_encoded=True)
        elif event.get('headers', {}).get('content-type', '').startswith('application/x-www-form-urlencoded'):
            # Handle regular form data
            form_data = parse_form_data(event['body'])
        else:
            # Try to parse as JSON
            try:
                form_data = json.loads(event['body'])
            except:
                print("Failed to parse body as JSON, trying as form data")
                form_data = parse_form_data(event['body'])
        
        print(f"Parsed form data: {form_data}")
        
        # Extract fields (support both naming conventions)
        name = form_data.get('name', form_data.get('organizationName', '')).strip()
        website = form_data.get('website', form_data.get('url', '')).strip()
        ical_url = form_data.get('ical_url', form_data.get('icalUrl', '')).strip()
        
        # Validate inputs
        if not name or not ical_url:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Organization name and iCal URL are required'})
            }
        
        # Get user profile information
        user_pool_id = os.environ['USER_POOL_ID']
        
        try:
            user_response = cognito.admin_get_user(
                UserPoolId=user_pool_id,
                Username=user_id
            )
            
            # Extract user attributes
            user_attrs = {}
            for attr in user_response.get('UserAttributes', []):
                user_attrs[attr['Name']] = attr['Value']
            
            # Try different attribute names for name
            submitter_name = user_attrs.get('name', 
                            user_attrs.get('custom:name', 
                            user_attrs.get('custom:nickname', '')))
            
            submitter_website = user_attrs.get('website', 
                               user_attrs.get('custom:website', ''))
            
            # Check if profile is complete (has a name)
            if not submitter_name:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'Complete profile required to submit sources'})
                }
                
        except Exception as e:
            print(f"Error getting user profile: {str(e)}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Error retrieving user profile'})
            }
        
        # Create source item
        source_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        source_item = {
            'id': source_id,
            'name': name,
            'website': website,
            'ical_url': ical_url,
            'approval_status': 'submitted',
            'submitted_by': user_id,
            'submitter_name': submitter_name,
            'submitter_website': submitter_website,
            'created_at': timestamp,
            'updated_at': timestamp
        }
        
        # Save to DynamoDB
        sources_table.put_item(Item=source_item)
        
        return {
            'statusCode': 201,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'message': 'Source submitted successfully',
                'id': source_id
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Internal server error: {str(e)}'})
        }
