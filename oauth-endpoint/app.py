from chalice import Chalice, Response
import os
import requests
import boto3
import json
import base64

app = Chalice(app_name='dctech-events-submit')
app.debug = False

# GitHub OAuth Client ID (public, can be hardcoded)
GITHUB_CLIENT_ID = 'Ov23liSTVbSKSvkYW6yg'

# AWS Secrets Manager client (lazy initialization)
_secrets_client = None

def get_secrets_client():
    """Get or create AWS Secrets Manager client."""
    global _secrets_client
    if _secrets_client is None:
        _secrets_client = boto3.client('secretsmanager')
    return _secrets_client

def get_github_secret():
    """
    Retrieve GitHub OAuth client secret from AWS Secrets Manager.
    Secret is expected to be stored at: dctech-events/github-oauth-secret
    """
    try:
        client = get_secrets_client()
        response = client.get_secret_value(SecretId='dctech-events/github-oauth-secret')

        # Secret can be stored as plain text or JSON
        if 'SecretString' in response:
            secret_value = response['SecretString']
            # Try to parse as JSON first
            try:
                secret_json = json.loads(secret_value)
                return secret_json.get('client_secret') or secret_json.get('secret')
            except (json.JSONDecodeError, TypeError):
                # If not JSON, treat as plain text
                return secret_value
        else:
            # Binary secret
            return response['SecretBinary']
    except Exception as e:
        print(f"Error retrieving GitHub secret from Secrets Manager: {str(e)}")
        return None

def decode_state_parameter(state):
    """
    Decode and validate the state parameter.

    The state parameter is a base64-encoded JSON object containing:
    - csrf_token: Random token for CSRF protection
    - return_url: URL to redirect to after OAuth (e.g., '/submit/' or '/submit-group/')
    - city: City slug (e.g., 'dc', 'sf') - OPTIONAL, defaults to 'dc'

    Returns:
        dict: Decoded state data with 'csrf_token', 'return_url', and 'city' keys
        None: If state is invalid or cannot be decoded
    """
    if not state:
        return None

    try:
        # Decode base64
        decoded_bytes = base64.b64decode(state)
        decoded_str = decoded_bytes.decode('utf-8')

        # Parse JSON
        state_data = json.loads(decoded_str)

        # Validate required fields
        if 'csrf_token' not in state_data or 'return_url' not in state_data:
            print(f"Invalid state data: missing required fields")
            return None

        # Validate return_url is one of the allowed paths
        # Allow /edit/ paths including those with hash fragments (e.g., /edit/event/#abc123)
        allowed_paths = ['/submit/', '/submit-group/', '/groups/edit/']
        return_url = state_data['return_url']
        is_edit_path = return_url.startswith('/edit/') and (return_url.endswith('/') or '#' in return_url)
        if return_url not in allowed_paths and not is_edit_path:
            print(f"Invalid return URL in state: {state_data['return_url']}")
            return None

        # City is optional, defaults to 'dc'
        if 'city' not in state_data:
            state_data['city'] = 'dc'

        # Validate city format (alphanumeric and dash only)
        if not state_data['city'].replace('-', '').isalnum():
            print(f"Invalid city format: {state_data['city']}")
            state_data['city'] = 'dc'

        return state_data

    except (base64.binascii.Error, json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
        print(f"Error decoding state parameter: {str(e)}")
        return None

@app.route('/oauth/callback', methods=['GET'])
def oauth_callback():
    """
    Handle GitHub OAuth callback
    Exchange authorization code for access token

    The state parameter is a base64-encoded JSON object containing:
    - csrf_token: Random token for CSRF protection
    - return_url: URL to redirect to after OAuth (e.g., '/submit/' or '/submit-group/')
    """
    # Get authorization code from query params
    code = app.current_request.query_params.get('code') if app.current_request.query_params else None
    state = app.current_request.query_params.get('state') if app.current_request.query_params else None
    error = app.current_request.query_params.get('error') if app.current_request.query_params else None

    # Decode and validate state parameter
    # Default to /submit/ if state is invalid or missing (for backward compatibility)
    state_data = decode_state_parameter(state)
    return_url = state_data['return_url'] if state_data else '/submit/'
    city = state_data['city'] if state_data else 'dc'

    # Build base URL for redirect
    # Map city slugs to their actual domains
    # DC uses dctech.events (legacy domain), other cities use {city}.localtech.events
    if city == 'dc':
        base_url = 'https://dctech.events'
    else:
        base_url = f'https://{city}.localtech.events'

    # Handle errors
    if error:
        return Response(
            body='',
            status_code=302,
            headers={
                'Location': f'{base_url}{return_url}?error={error}'
            }
        )

    if not code:
        return Response(
            body='',
            status_code=302,
            headers={
                'Location': f'{base_url}{return_url}?error=missing_code'
            }
        )

    # Get OAuth credentials
    client_id = GITHUB_CLIENT_ID
    client_secret = get_github_secret()

    if not client_id or not client_secret:
        return Response(
            body='',
            status_code=302,
            headers={
                'Location': f'{base_url}{return_url}?error=oauth_not_configured'
            }
        )

    # Exchange code for access token
    try:
        token_response = requests.post(
            'https://github.com/login/oauth/access_token',
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            json={
                'client_id': client_id,
                'client_secret': client_secret,
                'code': code,
                'state': state
            }
        )

        token_data = token_response.json()

        if 'error' in token_data:
            return Response(
                body='',
                status_code=302,
                headers={
                    'Location': f'{base_url}{return_url}?error={token_data["error"]}'
                }
            )

        access_token = token_data.get('access_token')

        if not access_token:
            return Response(
                body='',
                status_code=302,
                headers={
                    'Location': f'{base_url}{return_url}?error=no_token'
                }
            )

        # Redirect back to the city site with the access token
        return Response(
            body='',
            status_code=302,
            headers={
                'Location': f'{base_url}{return_url}?access_token={access_token}'
            }
        )

    except Exception as e:
        print(f"OAuth error: {str(e)}")
        return Response(
            body='',
            status_code=302,
            headers={
                'Location': f'{base_url}{return_url}?error=exchange_failed'
            }
        )

