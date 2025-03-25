import os
import json
import boto3
import urllib.parse
from botocore.exceptions import ClientError

cognito = boto3.client('cognito-idp')

def handler(event, context):
    try:
        print("Event received:", json.dumps(event, default=str))
        
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
            print("USER_POOL_ID environment variable not set")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'text/html'},
                'body': '<div class="error-message">Server configuration error</div>'
            }
        
        print(f"Updating profile for user with sub: {user_sub}")
        
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
        
        # Extract and validate profile fields
        nickname = form_data.get('nickname', '').strip()
        website = form_data.get('website', '').strip()
        
        if not nickname:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'text/html'},
                'body': '<div class="error-message">Display name is required</div>'
            }
        
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
            
            # Get the username
            username = response['Users'][0]['Username']
            
            # Prepare user attributes update
            user_attributes = [
                {
                    'Name': 'custom:nickname',
                    'Value': nickname
                },
                {
                    'Name': 'custom:website',
                    'Value': website
                },
                {
                    'Name': 'custom:profile_complete',
                    'Value': 'true'
                }
            ]
            
            # Update user attributes in Cognito
            cognito.admin_update_user_attributes(
                UserPoolId=user_pool_id,
                Username=username,
                UserAttributes=user_attributes
            )
            
            # Get the updated user data to display in the form
            user_response = cognito.admin_get_user(
                UserPoolId=user_pool_id,
                Username=username
            )
            
            # Extract user attributes
            updated_attributes = {}
            for attr in user_response['UserAttributes']:
                name = attr['Name']
                value = attr['Value']
                
                # Convert custom: prefix attributes to a cleaner format
                if name.startswith('custom:'):
                    name = name[7:]  # Remove 'custom:' prefix
                
                updated_attributes[name] = value
            
            # Create profile object with required fields
            profile = {
                'email': username,  # Use username as email
                'nickname': updated_attributes.get('nickname', ''),
                'website': updated_attributes.get('website', ''),
                'profile_complete': updated_attributes.get('profile_complete', 'false') == 'true'
            }
            
            # Return success message with updated form
            success_html = f"""
            <div id="profile-container">
                <div class="success-message">
                    <h3>Profile Updated</h3>
                    <p>Your profile has been successfully updated.</p>
                </div>
                
                <h2>Your Profile</h2>
                <form id="profile-form" hx-put="/api/profile" hx-target="#profile-container" hx-swap="outerHTML">
                    <div class="form-group">
                        <label for="email">Email:</label>
                        <input type="email" id="email" name="email" value="{profile['email']}" readonly>
                        <small>Email cannot be changed</small>
                    </div>
                    
                    <div class="form-group">
                        <label for="nickname">Display Name:</label>
                        <input type="text" id="nickname" name="nickname" value="{profile['nickname']}" required>
                        <small>This name will be displayed publicly with your events</small>
                    </div>
                    
                    <div class="form-group">
                        <label for="website">Website (optional):</label>
                        <input type="url" id="website" name="website" value="{profile['website']}" 
                               placeholder="https://example.com">
                        <small>Your personal or organization website</small>
                    </div>
                    
                    <button type="submit">
                        <span class="htmx-indicator">
                            <div class="loading-spinner"></div> Saving...
                        </span>
                        <span class="submit-text">Save Profile</span>
                    </button>
                </form>
            </div>
            """
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'text/html',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                    'Access-Control-Allow-Methods': 'PUT,OPTIONS',
                },
                'body': success_html
            }
            
        except ClientError as e:
            print(f"Error updating user attributes: {str(e)}")
            error_html = f"""
            <div class="error-message">
                <h3>Error</h3>
                <p>There was a problem updating your profile: {str(e)}</p>
            </div>
            """
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'text/html'},
                'body': error_html
            }
            
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'text/html'},
            'body': f'<div class="error-message">An unexpected error occurred: {str(e)}</div>'
        }
