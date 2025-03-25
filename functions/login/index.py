import os
import json
import boto3
import urllib.parse
from botocore.exceptions import ClientError

cognito = boto3.client('cognito-idp')

def handler(event, context):
    try:
        print("Login request received")
        print("Event:", json.dumps(event, default=str))
        
        # Parse form data from the request body
        body = event.get('body', '')
        is_base64_encoded = event.get('isBase64Encoded', False)
        
        if is_base64_encoded:
            import base64
            body = base64.b64decode(body).decode('utf-8')
        
        print("Request body:", body)
        
        # Parse form data
        form_data = {}
        if body:
            pairs = urllib.parse.parse_qs(body)
            for key, values in pairs.items():
                form_data[key] = values[0] if values else ''
        
        print("Parsed form data:", json.dumps(form_data, default=str))
        
        # Extract login credentials
        email = form_data.get('email', '').strip()
        password = form_data.get('password', '')
        redirect_url = form_data.get('redirect-url', '/')
        
        print(f"Email: {email}, Redirect URL: {redirect_url}")
        
        if not email or not password:
            print("Missing email or password")
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                    'Access-Control-Allow-Methods': 'POST,OPTIONS'
                },
                'body': json.dumps({
                    'error': 'Email and password are required'
                })
            }
        
        # Get the user pool ID and client ID from environment variables
        user_pool_id = os.environ.get('USER_POOL_ID')
        client_id = os.environ.get('CLIENT_ID')
        
        print(f"Using USER_POOL_ID: {user_pool_id}, CLIENT_ID: {client_id}")
        
        if not user_pool_id or not client_id:
            print("Missing environment variables: USER_POOL_ID or CLIENT_ID")
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                    'Access-Control-Allow-Methods': 'POST,OPTIONS'
                },
                'body': json.dumps({
                    'error': 'Server configuration error'
                })
            }
        
        try:
            # Authenticate the user
            print(f"Authenticating user: {email}")
            response = cognito.admin_initiate_auth(
                UserPoolId=user_pool_id,
                ClientId=client_id,
                AuthFlow='ADMIN_NO_SRP_AUTH',
                AuthParameters={
                    'USERNAME': email,
                    'PASSWORD': password
                }
            )
            
            print("Authentication successful")
            
            # Extract the token
            auth_result = response.get('AuthenticationResult', {})
            id_token = auth_result.get('IdToken')
            refresh_token = auth_result.get('RefreshToken')
            
            if not id_token:
                print("No ID token in authentication result")
                return {
                    'statusCode': 401,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                        'Access-Control-Allow-Methods': 'POST,OPTIONS'
                    },
                    'body': json.dumps({
                        'error': 'Authentication failed'
                    })
                }
            
            # Return the token and redirect URL
            print(f"Returning tokens to client with redirect URL: {redirect_url}")
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                    'Access-Control-Allow-Methods': 'POST,OPTIONS'
                },
                'body': json.dumps({
                    'token': id_token,
                    'refreshToken': refresh_token,
                    'redirectUrl': redirect_url
                })
            }
            
        except cognito.exceptions.NotAuthorizedException as e:
            print(f"Invalid credentials: {str(e)}")
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                    'Access-Control-Allow-Methods': 'POST,OPTIONS'
                },
                'body': json.dumps({
                    'error': 'Invalid email or password'
                })
            }
            
        except cognito.exceptions.UserNotFoundException as e:
            print(f"User not found: {str(e)}")
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                    'Access-Control-Allow-Methods': 'POST,OPTIONS'
                },
                'body': json.dumps({
                    'error': 'Invalid email or password'
                })
            }
            
        except ClientError as e:
            print(f"Cognito error: {str(e)}")
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                    'Access-Control-Allow-Methods': 'POST,OPTIONS'
                },
                'body': json.dumps({
                    'error': 'Authentication service error'
                })
            }
            
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                'Access-Control-Allow-Methods': 'POST,OPTIONS'
            },
            'body': json.dumps({
                'error': 'An unexpected error occurred'
            })
        }
