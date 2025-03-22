import json
import boto3
import secrets
import string

def generate_temp_password():
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for i in range(20))

def handler(event, context):
    print("Event:", event)
    
    if event['triggerSource'] == "DefineAuthChallenge_Authentication":
        email = event['request']['userAttributes'].get('email', event['userName'])
        cognito = boto3.client('cognito-idp')
        
        try:
            # Check if user exists
            cognito.admin_get_user(
                UserPoolId=event['userPoolId'],
                Username=email
            )
        except cognito.exceptions.UserNotFoundException:
            # Create the user if they don't exist
            temp_password = generate_temp_password()
            try:
                cognito.admin_create_user(
                    UserPoolId=event['userPoolId'],
                    Username=email,
                    UserAttributes=[
                        {'Name': 'email', 'Value': email},
                        {'Name': 'email_verified', 'Value': 'false'}
                    ],
                    MessageAction='SUPPRESS',
                    TemporaryPassword=temp_password
                )
                
                # Immediately set a permanent password
                cognito.admin_set_user_password(
                    UserPoolId=event['userPoolId'],
                    Username=email,
                    Password=temp_password,
                    Permanent=True
                )
                print(f"Created new user: {email}")
            except Exception as e:
                print(f"Error creating user: {str(e)}")
                raise e

        # Define the authentication challenge
        if event['request']['session']:
            # If we have a session with challenges
            session = event['request']['session']
            
            # Check if this is the first challenge
            if len(session) == 0:
                event['response']['challengeName'] = 'CUSTOM_CHALLENGE'
                event['response']['issueTokens'] = False
                event['response']['failAuthentication'] = False
                
            # Check the last challenge
            elif len(session) == 1 and session[-1]['challengeName'] == 'CUSTOM_CHALLENGE':
                if session[-1]['challengeResult'] == True:
                    event['response']['issueTokens'] = True
                    event['response']['failAuthentication'] = False
                else:
                    event['response']['issueTokens'] = False
                    event['response']['failAuthentication'] = True
            else:
                event['response']['issueTokens'] = False
                event['response']['failAuthentication'] = True
        else:
            # Start with a custom challenge
            event['response']['challengeName'] = 'CUSTOM_CHALLENGE'
            event['response']['issueTokens'] = False
            event['response']['failAuthentication'] = False

    print("Response:", event['response'])
    return event
