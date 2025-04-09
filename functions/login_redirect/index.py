import os
import json
import urllib.parse

def handler(event, context):
    """
    Redirects to the Cognito hosted UI login page
    """
    # Get environment variables
    user_pool_id = os.environ.get('USER_POOL_ID')
    client_id = os.environ.get('CLIENT_ID')
    domain = os.environ.get('DOMAIN')
    
    # Default redirect URL after login
    redirect_uri = "https://dctech.events/static/callback.html"
    
    # Check if a specific redirect URL was provided in the query parameters
    if event.get('queryStringParameters') and event.get('queryStringParameters').get('redirect_uri'):
        provided_redirect = event.get('queryStringParameters').get('redirect_uri')
        # Validate the redirect URI against allowed domains
        allowed_domains = [
            "https://dctech.events",
            "https://www.dctech.events",
            "http://localhost:3000"
        ]
        if any(provided_redirect.startswith(domain) for domain in allowed_domains):
            redirect_uri = provided_redirect
    
    # Construct the login URL
    login_url = f"https://{domain}/login"
    
    # Add query parameters
    query_params = {
        'client_id': client_id,
        'response_type': 'code',
        'scope': 'email openid profile',  # Space-separated scopes, will be properly encoded
        'redirect_uri': redirect_uri
    }
    
    login_url += "?" + urllib.parse.urlencode(query_params)
    
    # Return a redirect response
    return {
        'statusCode': 302,
        'headers': {
            'Location': login_url,
            'Cache-Control': 'no-cache'
        },
        'body': json.dumps({
            'message': 'Redirecting to login page'
        })
    }
