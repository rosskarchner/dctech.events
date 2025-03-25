import os
import json
import boto3
import uuid
import urllib.parse
from datetime import datetime, UTC

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])
cognito = boto3.client('cognito-idp')

def handler(event, context):
    try:
        # Extract user information from the JWT claims
        claims = event.get('requestContext', {}).get('authorizer', {}).get('jwt', {}).get('claims', {})
        
        if not claims:
            print("No JWT claims found in the request")
            return {
                'statusCode': 401,
                'headers': {'Content-Type': 'text/html'},
                'body': '<div class="error-message">Authentication required</div>'
            }
        
        # Get user identifier - prefer sub over email since sub is always present
        user_sub = claims.get('sub')
        
        if not user_sub:
            print("No sub found in JWT claims")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'text/html'},
                'body': '<div class="error-message">User identifier not found in token</div>'
            }
            
        user_pool_id = os.environ.get('USER_POOL_ID')
        
        if not user_pool_id:
            # Try to extract from issuer if environment variable not set
            issuer = event.get('requestContext', {}).get('authorizer', {}).get('jwt', {}).get('issuer')
            if issuer:
                user_pool_id = issuer.split('/')[-1]
            
            if not user_pool_id:
                print("Could not determine USER_POOL_ID")
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'text/html'},
                    'body': '<div class="error-message">Server configuration error</div>'
                }
        
        print(f"User submitting event with sub: {user_sub}")
        
        # Check if user has completed their profile
        try:
            # First, find the user by sub
            response = cognito.list_users(
                UserPoolId=user_pool_id,
                Filter=f'sub = "{user_sub}"',
                Limit=1
            )
            
            if not response.get('Users') or len(response['Users']) == 0:
                print(f"No user found with sub: {user_sub}")
                return {
                    'statusCode': 404,
                    'headers': {'Content-Type': 'text/html'},
                    'body': '<div class="error-message">User not found</div>'
                }
            
            # Get the user attributes
            user = response['Users'][0]
            
            # Extract profile_complete attribute
            profile_complete = False
            for attr in user['Attributes']:
                if attr['Name'] == 'custom:profile_complete':
                    profile_complete = attr['Value'].lower() == 'true'
                    break
            
            if not profile_complete:
                return {
                    'statusCode': 403,
                    'headers': {'Content-Type': 'text/html'},
                    'body': """
                    <div class="error-message">
                        <h3>Profile Required</h3>
                        <p>You need to complete your profile before submitting events.</p>
                        <a href="/profile" class="btn-primary">Complete Your Profile</a>
                    </div>
                    """
                }
                
            # Continue with event submission...
            # Parse form data from the request body
            body = event.get('body', '')
            is_base64_encoded = event.get('isBase64Encoded', False)
            
            if is_base64_encoded:
                import base64
                body = base64.b64decode(body).decode('utf-8')
            
            # Parse form data
            form_data = {}
            if body:
                pairs = urllib.parse.parse_qs(body)
                for key, values in pairs.items():
                    form_data[key] = values[0] if values else ''
            
            # Extract event details
            title = form_data.get('title', '').strip()
            description = form_data.get('description', '').strip()
            event_date = form_data.get('date', '').strip()
            event_time = form_data.get('time', '').strip()
            location = form_data.get('location', '').strip()
            url = form_data.get('url', '').strip()
            
            # Validate required fields
            if not title or not description or not event_date:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'text/html'},
                    'body': '<div class="error-message">Title, description, and date are required</div>'
                }
            
            # Generate a unique ID for the event
            event_id = str(uuid.uuid4())
            
            # Parse the date to determine the week
            try:
                event_datetime = datetime.strptime(f"{event_date} {event_time or '00:00'}", "%Y-%m-%d %H:%M")
                week_start = event_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
                while week_start.weekday() != 0:  # 0 is Monday
                    week_start = week_start.replace(day=week_start.day - 1)
                
                week_key = week_start.strftime("%Y-%m-%d")
            except ValueError:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'text/html'},
                    'body': '<div class="error-message">Invalid date format</div>'
                }
            
            # Get user's display name
            nickname = ""
            for attr in user['Attributes']:
                if attr['Name'] == 'custom:nickname':
                    nickname = attr['Value']
                    break
            
            # Create the event item
            event_item = {
                'week': week_key,
                'sort': f"EVENT#{event_datetime.strftime('%Y-%m-%dT%H:%M:%S')}#{event_id}",
                'id': event_id,
                'title': title,
                'description': description,
                'date': event_date,
                'time': event_time,
                'location': location,
                'url': url,
                'status': 'pending',
                'submitter_id': user_sub,
                'submitter_name': nickname,
                'created_at': datetime.now(UTC).isoformat(),
                'updated_at': datetime.now(UTC).isoformat()
            }
            
            # Save to DynamoDB
            table.put_item(Item=event_item)
            
            # Return success message
            success_html = """
            <div class="success-message">
                <h3>Event Submitted</h3>
                <p>Your event has been submitted for review. It will appear on the site after approval.</p>
                <a href="/" class="btn-primary">Back to Home</a>
            </div>
            """
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'text/html'},
                'body': success_html
            }
            
        except Exception as e:
            print(f"Error checking user profile: {str(e)}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'text/html'},
                'body': f'<div class="error-message">Error checking user profile: {str(e)}</div>'
            }
            
    except Exception as e:
        print(f"Error submitting event: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'text/html'},
            'body': f'<div class="error-message">Error submitting event: {str(e)}</div>'
        }
