import json
import os
import time
import base64
import boto3
import urllib.request
import jwt


# Get the User Pool ID from environment variables
USER_POOL_ID = os.environ.get('USER_POOL_ID')
CLIENT_ID = os.environ.get('CLIENT_ID')
REGION = os.environ.get('AWS_REGION', 'us-east-1')

# Cache the JWKS (JSON Web Key Set)
jwks = None

def get_jwks():
    global jwks
    if not jwks:
        jwks_url = f'https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json'
        with urllib.request.urlopen(jwks_url) as response:
            jwks = json.loads(response.read())
    return jwks

def handler(event, context):
    try:
        print("Event:", json.dumps(event))
        
        # Get the methodArn or routeArn from the event
        resource_arn = event.get('routeArn') or event.get('methodArn')
        if not resource_arn:
            print("No routeArn or methodArn found in event")
            # Use a default resource ARN if none is provided
            resource_arn = f"arn:aws:execute-api:{REGION}:*:*/*/*/*"
        
        # Get cookies from the request
        cookies = {}
        if 'headers' in event and event['headers'] and 'Cookie' in event['headers']:
            for cookie in event['headers']['Cookie'].split(';'):
                if '=' in cookie:
                    name, value = cookie.strip().split('=', 1)
                    cookies[name] = value
        
        # Check for access_token and id_token in cookies
        access_token = cookies.get('access_token')
        id_token = cookies.get('id_token')
        
        if not access_token:
            print("No access_token found in cookies")
            return generate_policy(None, 'Deny', resource_arn)
            
        if not id_token:
            print("No id_token found in cookies")
            # We'll continue with just the access token, but won't have the ID token data
        
        try:
            # Get the key set
            keys = get_jwks()
            
            # First decode access token without verification to get the key ID
            access_header = jwt.get_unverified_header(access_token)
            access_kid = access_header['kid']
            
            # Find the correct key for access token
            access_key = None
            for k in keys['keys']:
                if k['kid'] == access_kid:
                    access_key = k
                    break
            
            if not access_key:
                print("Public key not found in JWKS for access token")
                raise Exception("Public key not found in JWKS for access token")
            
            # Convert the key to PEM format
            access_public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(access_key))
            
            # Decode and verify the access token - skip audience validation for access tokens
            access_payload = jwt.decode(
                access_token,
                access_public_key,
                algorithms=['RS256'],
                options={
                    "verify_exp": True,
                    "verify_aud": False  # Skip audience validation for access tokens
                },
                issuer=f'https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}'
            )
            
            # Get user information from the access token
            user_id = access_payload.get('sub')
            if not user_id:
                print("No user_id (sub) found in access token payload")
                return generate_policy(None, 'Deny', resource_arn)
            
            # Access token is valid
            print(f"Access token is valid for user {user_id}")
            
            # Now decode the ID token to get additional user information
            id_token_payload = {}
            if id_token:
                try:
                    # Decode ID token without verification to get the key ID
                    id_header = jwt.get_unverified_header(id_token)
                    id_kid = id_header['kid']
                    
                    # Find the correct key for ID token
                    id_key = None
                    for k in keys['keys']:
                        if k['kid'] == id_kid:
                            id_key = k
                            break
                    
                    if id_key:
                        # Convert the key to PEM format
                        id_public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(id_key))
                        
                        # Decode and verify the ID token
                        id_token_payload = jwt.decode(
                            id_token,
                            id_public_key,
                            algorithms=['RS256'],
                            options={"verify_exp": True},
                            audience=CLIENT_ID,
                            issuer=f'https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}'
                        )
                        print("Successfully decoded ID token")
                    else:
                        print("Public key not found in JWKS for ID token")
                except Exception as e:
                    print(f"Error decoding ID token: {str(e)}")
                    # Continue with just the access token data
            
            # Combine data from both tokens, with access token taking precedence for overlapping fields
            combined_payload = {**id_token_payload, **access_payload}
            
            # Include all token fields in the context
            return generate_policy(user_id, 'Allow', resource_arn, combined_payload)
            
        except jwt.ExpiredSignatureError:
            print("Token has expired")
            return generate_policy(None, 'Deny', resource_arn)
        except jwt.InvalidTokenError as e:
            print(f"Invalid token: {str(e)}")
            return generate_policy(None, 'Deny', resource_arn)
        except Exception as e:
            print(f"Token verification error: {str(e)}")
            return generate_policy(None, 'Deny', resource_arn)
            
    except Exception as e:
        print(f"Error in authorizer: {str(e)}")
        return generate_policy(None, 'Deny', resource_arn if 'resource_arn' in locals() else "*")

def generate_policy(principal_id, effect, resource, context=None):
    auth_response = {
        'principalId': principal_id or 'user'
    }
    
    if effect and resource:
        auth_response['policyDocument'] = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': effect,
                    'Resource': resource
                }
            ]
        }
    
    # Include all token fields in the context
    if context:
        # Create a context object with all fields from the token
        auth_context = {}
        
        # Add all fields from the token payload
        for key, value in context.items():
            # Convert lists and dictionaries to strings
            if isinstance(value, (list, dict)):
                value = json.dumps(value)
            # Convert other non-string values to strings
            elif not isinstance(value, str):
                value = str(value)
                
            # API Gateway context values must be strings and can't exceed 3583 bytes
            if len(value) > 3500:  # Leave some buffer
                value = value[:3500] + "..."
                
            # Replace any characters that might cause issues
            safe_key = key.replace(':', '_').replace('.', '_')
            auth_context[safe_key] = value
        
        # Ensure we have the basic fields
        if 'sub' in context and 'sub' not in auth_context:
            auth_context['sub'] = context['sub']
        if 'email' in context and 'email' not in auth_context:
            auth_context['email'] = context['email']
            
        auth_response['context'] = auth_context
    
    return auth_response
