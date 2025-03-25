import json
import boto3
import re
import secrets
import string

def generate_temp_password():
    # Generate a secure temporary password
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for i in range(16))

def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def handler(event, context):
    print("Event:", event)  # Helpful for debugging
    
    if event['triggerSource'] == 'PreSignUp_SignUp':
        # Get the email from the sign-up request
        email = event['request']['userAttributes'].get('email')
        
        if not email:
            print("No email provided in sign-up request")
            raise Exception("Email is required for sign-up")
            
        if not is_valid_email(email):
            print(f"Invalid email format: {email}")
            raise Exception("Invalid email format")
            
        cognito = boto3.client('cognito-idp')
        
        try:
            # Try to get the user - if this succeeds, they exist
            cognito.admin_get_user(
                UserPoolId=event['userPoolId'],
                Username=email
            )
            print(f"User already exists: {email}")
            
        except cognito.exceptions.UserNotFoundException:
            # User doesn't exist, create them
            try:
                temp_password = generate_temp_password()
                cognito.admin_create_user(
                    UserPoolId=event['userPoolId'],
                    Username=email,
                    UserAttributes=[
                        {
                            'Name': 'email',
                            'Value': email
                        },
                        {
                            'Name': 'email_verified',
                            'Value': 'false'
                        },
                        {
                            'Name': 'custom:profile_complete',
                            'Value': 'false'
                        }
                    ],
                    MessageAction='SUPPRESS',  # Don't send welcome email
                    TemporaryPassword=temp_password
                )
                
                # Set the password to make the user complete
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
        
        # Auto-create the user by allowing the sign-up
        event['response']['autoConfirmUser'] = True
        
        # Don't auto-verify email - this will happen after they enter the code
        event['response']['autoVerifyEmail'] = False
        
        print(f"Auto-confirmed user with email: {email}")
        
    print("Response:", event['response'])
    return event
