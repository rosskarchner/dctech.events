import json
import os
import boto3
import urllib.parse
import time
from urllib.parse import parse_qs, urlparse

# Initialize AWS clients
cognito = boto3.client('cognito-idp')
s3 = boto3.client('s3')

# Get environment variables
USER_POOL_ID = os.environ.get('USER_POOL_ID')
CLIENT_ID = os.environ.get('CLIENT_ID')
VERIFICATION_BUCKET_NAME = os.environ.get('VERIFICATION_BUCKET_NAME')

def handler(event, context):
    try:
        # Log the event for debugging
        print('Event:', event)
        
        # Get code from query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        code = query_params.get('code')
        
        if not code:
            return redirect_response('/login?error=invalid_link')
        
        # Get the verification data from S3
        try:
            if VERIFICATION_BUCKET_NAME:
                response = s3.get_object(
                    Bucket=VERIFICATION_BUCKET_NAME,
                    Key=f"codes/{code}.json"
                )
                
                verification_data = json.loads(response['Body'].read().decode('utf-8'))
                user_sub = verification_data.get('user_sub')
                email = verification_data.get('email')
                session = verification_data.get('session')
                redirect = verification_data.get('redirect', '/')
                expires_at = verification_data.get('expires_at', 0)
                
                # Check if the code has expired
                if time.time() > expires_at:
                    print(f"Code {code} has expired")
                    return redirect_response('/login?error=expired_link')
                
                print(f"Found verification data for code {code}: user_sub={user_sub}, email={email}")
            else:
                print("No verification bucket configured")
                return redirect_response('/login?error=configuration_error')
        except Exception as e:
            print(f"Error retrieving verification data from S3: {str(e)}")
            return redirect_response('/login?error=invalid_code')
        
        # Start a new auth session
        try:
            auth_response = cognito.admin_initiate_auth(
                UserPoolId=USER_POOL_ID,
                ClientId=CLIENT_ID,
                AuthFlow='CUSTOM_AUTH',
                AuthParameters={
                    'USERNAME': email
                }
            )
            
            new_session = auth_response.get('Session', '')
            if not new_session:
                print("Failed to get a new session")
                return redirect_response('/login?error=session_creation_failed')
                
            print(f"Created new session: {new_session[:20]}...")
            
        except Exception as e:
            print(f"Error initiating auth: {str(e)}")
            return redirect_response('/login?error=auth_initiation_failed')
        
        # Respond to the challenge with the code using the new session
        try:
            print(f"Responding to challenge for email: {email}")
            challenge_response = cognito.admin_respond_to_auth_challenge(
                UserPoolId=USER_POOL_ID,
                ClientId=CLIENT_ID,
                ChallengeName='CUSTOM_CHALLENGE',
                ChallengeResponses={
                    'USERNAME': email,
                    'ANSWER': code
                },
                Session=new_session
            )
            
            print(f"Challenge response: {json.dumps(challenge_response)}")
        except Exception as e:
            print(f"Error responding to challenge: {str(e)}")
            return redirect_response('/login?error=invalid_code_or_expired_session')
        
        # Check if authentication was successful
        if 'AuthenticationResult' in challenge_response:
            # Get tokens from the challenge response
            id_token = challenge_response['AuthenticationResult']['IdToken']
            access_token = challenge_response['AuthenticationResult']['AccessToken']
            refresh_token = challenge_response['AuthenticationResult']['RefreshToken']
            
            # Delete the verification code from S3 after successful use
            try:
                s3.delete_object(
                    Bucket=VERIFICATION_BUCKET_NAME,
                    Key=f"codes/{code}.json"
                )
                print(f"Deleted verification code {code} from S3")
            except Exception as e:
                print(f"Error deleting verification code from S3: {str(e)}")
            
            # Using API Gateway HTTP API payload format 2.0 to set multiple cookies
            return {
                'cookies': [
                    f"id_token={id_token}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=3600",
                    f"access_token={access_token}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=3600",
                    f"refresh_token={refresh_token}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=86400"
                ],
                'statusCode': 302,
                'headers': {
                    'Location': redirect
                }
            }
        else:
            print(f"No authentication result in challenge response")
            return redirect_response('/login?error=auth_failed')
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return redirect_response('/login?error=server_error')

def redirect_response(location):
    return {
        'statusCode': 302,
        'headers': {
            'Location': location,
            'Content-Type': 'text/html'
        },
        'body': f'<html><head><title>Redirecting...</title></head><body>Redirecting to <a href="{location}">{location}</a>...</body></html>'
    }
