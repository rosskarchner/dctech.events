import os
import json
import boto3
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
        
        print(f"Getting profile for user with sub: {user_sub}")
        
        # Get user attributes from Cognito using the sub as identifier
        try:
            # First, list users to find the one with matching sub
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
            
            # Get the username and attributes
            user = response['Users'][0]
            username = user['Username']
            user_attributes = {}
            
            # Extract email from attributes
            user_email = None
            for attr in user['Attributes']:
                name = attr['Name']
                value = attr['Value']
                
                if name == 'email':
                    user_email = value
                
                # Convert custom: prefix attributes to a cleaner format
                if name.startswith('custom:'):
                    name = name[7:]  # Remove 'custom:' prefix
                
                user_attributes[name] = value
            
            if not user_email:
                user_email = username  # Fallback to username if email not found
            
            # Create profile object with required fields
            profile = {
                'email': user_email,
                'nickname': user_attributes.get('nickname', ''),
                'website': user_attributes.get('website', ''),
                'profile_complete': user_attributes.get('profile_complete', 'false') == 'true'
            }
            
            # Return profile data as HTML for the profile page
            profile_html = f"""
            <div id="profile-container">
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
                    'Access-Control-Allow-Methods': 'GET,OPTIONS',
                },
                'body': profile_html
            }
            
        except ClientError as e:
            print(f"Error getting user: {str(e)}")
            error_html = f"""
            <div class="error-message">
                <h3>Error</h3>
                <p>There was a problem retrieving your profile: {str(e)}</p>
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
