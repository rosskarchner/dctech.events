import json
import os
import boto3
import urllib.parse
import random
import string
import time
from botocore.exceptions import ClientError

# Initialize AWS clients
cognito = boto3.client('cognito-idp')
ses = boto3.client('ses')
s3 = boto3.client('s3')

# Get environment variables
USER_POOL_ID = os.environ.get('USER_POOL_ID')
CLIENT_ID = os.environ.get('CLIENT_ID')
EMAIL_FROM = os.environ.get('EMAIL_FROM')
BASE_URL = os.environ.get('BASE_URL', 'https://dctech.events')
VERIFICATION_BUCKET_NAME = os.environ.get('VERIFICATION_BUCKET_NAME')

def handler(event, context):
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        email = body.get('email', '').lower().strip()
        redirect = body.get('redirect', '/')
        
        # Validate email
        if not is_valid_email(email):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'message': 'Invalid email address'})
            }
        
        # Check if user exists in Cognito
        try:
            user_response = cognito.admin_get_user(
                UserPoolId=USER_POOL_ID,
                Username=email
            )
            user_exists = True
            # Get the user's sub ID
            user_sub = None
            for attr in user_response.get('UserAttributes', []):
                if attr['Name'] == 'sub':
                    user_sub = attr['Value']
                    break
        except cognito.exceptions.UserNotFoundException:
            user_exists = False
        
        # If user doesn't exist, return an error
        if not user_exists:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'message': 'User not found. Please sign up first.'})
            }
        
        # Generate a random 6-digit code
        code = ''.join(random.choices(string.digits, k=6))
        
        # Initiate the custom auth flow
        auth_response = cognito.admin_initiate_auth(
            UserPoolId=USER_POOL_ID,
            ClientId=CLIENT_ID,
            AuthFlow='CUSTOM_AUTH',
            AuthParameters={
                'USERNAME': email
            }
        )
        
        # Extract the session for later use
        session = auth_response.get('Session', '')
        
        # Store the session and user info in S3 with the code as the key
        if VERIFICATION_BUCKET_NAME:
            try:
                # Store the data in S3
                s3.put_object(
                    Bucket=VERIFICATION_BUCKET_NAME,
                    Key=f"codes/{code}.json",
                    Body=json.dumps({
                        'user_sub': user_sub,
                        'email': email,
                        'session': session,
                        'redirect': redirect,
                        'created_at': int(time.time()),
                        'expires_at': int(time.time()) + 1800  # 30 minutes expiration
                    }),
                    ContentType='application/json'
                )
                print(f"Stored verification data in S3 with code {code}")
            except Exception as e:
                print(f"Error storing data in S3: {str(e)}")
                # Continue anyway, as we'll also use Cognito's challenge parameters
        
        # Generate magic link with just the code
        magic_link = f"{BASE_URL}/api/auth/verify?code={code}"
        
        # Send email with magic link
        try:
            send_magic_link_email(email, magic_link)
        except ClientError as e:
            print(f"Error sending email: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'message': f'Error sending email: {str(e)}'})
            }
        
        # Store the code in Cognito's session as a backup
        try:
            cognito.admin_respond_to_auth_challenge(
                UserPoolId=USER_POOL_ID,
                ClientId=CLIENT_ID,
                ChallengeName='CUSTOM_CHALLENGE',
                Session=session,
                ChallengeResponses={
                    'USERNAME': email,
                    'ANSWER': code
                }
            )
        except Exception as e:
            print(f"Error responding to auth challenge: {e}")
            # Continue anyway, as the code is in the magic link and S3
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'message': 'Magic link sent to your email',
                'redirect': redirect
            })
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'message': f'Internal server error: {str(e)}'})
        }

def is_valid_email(email):
    # Basic email validation
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def send_magic_link_email(email, magic_link):
    # Email content
    subject = "Your Magic Link for DC Tech Events"
    text_content = f"""
Hello,

Click the link below to sign in to DC Tech Events:

{magic_link}

This link will expire in 30 minutes.

If you didn't request this link, you can safely ignore this email.

Best regards,
DC Tech Events Team
"""
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .button {{ display: inline-block; padding: 10px 20px; background-color: #4CAF50; color: white; text-decoration: none; border-radius: 5px; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #777; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Sign in to DC Tech Events</h2>
        <p>Hello,</p>
        <p>Click the button below to sign in to DC Tech Events:</p>
        <p><a href="{magic_link}" class="button">Sign In</a></p>
        <p>Or copy and paste this link in your browser:</p>
        <p>{magic_link}</p>
        <p>This link will expire in 30 minutes.</p>
        <p>If you didn't request this link, you can safely ignore this email.</p>
        <div class="footer">
            <p>Best regards,<br>DC Tech Events Team</p>
        </div>
    </div>
</body>
</html>
"""
    
    # Send email using SES
    ses.send_email(
        Source=EMAIL_FROM,
        Destination={'ToAddresses': [email]},
        Message={
            'Subject': {'Data': subject},
            'Body': {
                'Text': {'Data': text_content},
                'Html': {'Data': html_content}
            }
        }
    )
