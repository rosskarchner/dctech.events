import os
import json
import boto3
import uuid
import urllib.parse
from datetime import datetime, UTC
from shared.template_utils import render_template, parse_form_data

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
                'body': render_template('error.mustache', {'message': 'Authentication required'})
            }
        
        # Get user identifier - prefer sub over email since sub is always present
        user_sub = claims.get('sub')
        
        if not user_sub:
            print("No sub found in JWT claims")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'text/html'},
                'body': render_template('error.mustache', {'message': 'User identifier not found in token'})
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
                    'body': render_template('error.mustache', {'message': 'Server configuration error'})
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
                    'body': render_template('error.mustache', {'message': 'User not found'})
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
                    'body': render_template('error.mustache', {
                        'message': 'Profile Required',
                        'details': 'You need to complete your profile before submitting events.',
                        'action_url': '/profile',
                        'action_text': 'Complete Your Profile'
                    })
                }
                
            # Continue with event submission...
            # Parse form data from the request body
            form_data = parse_form_data(event)
            
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
                    'body': render_template('error.mustache', {'message': 'Title, description, and date are required'})
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
                    'body': render_template('error.mustache', {'message': 'Invalid date format'})
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
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'text/html'},
                'body': render_template('success.mustache', {
                    'message': 'Event Submitted',
                    'details': 'Your event has been submitted for review. It will appear on the site after approval.',
                    'action_url': '/',
                    'action_text': 'Back to Home'
                })
            }
            
        except Exception as e:
            print(f"Error checking user profile: {str(e)}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'text/html'},
                'body': render_template('error.mustache', {'message': f'Error checking user profile: {str(e)}'})
            }
            
    except Exception as e:
        print(f"Error submitting event: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'text/html'},
            'body': render_template('error.mustache', {'message': f'Error submitting event: {str(e)}'})
        }
