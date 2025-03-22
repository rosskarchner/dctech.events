import json
import boto3
import os
import random
from botocore.exceptions import ClientError
import re

def is_valid_email(email):
    # Basic email validation
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def handler(event, context):
    print("Event:", event)  # Helpful for debugging
    
    if event['triggerSource'] == 'CreateAuthChallenge_Authentication':
        cognito = boto3.client('cognito-idp')
        
        try:
            # Get user details to find their email
            user = cognito.admin_get_user(
                UserPoolId=event['userPoolId'],  # Changed from user_pool_id to userPoolId
                Username=event['userName']
            )
            
            # Find the email from user attributes
            email = None
            for attr in user['UserAttributes']:
                if attr['Name'] == 'email':
                    email = attr['Value']
                    break
            
            if not email:
                print(f"No email found for user: {event['userName']}")
                raise Exception("No email address found for user")
                
            if not is_valid_email(email):
                print(f"Invalid email format: {email}")
                raise Exception("Invalid email format")
            
            # Generate a 6-digit code
            code = str(random.randint(100000, 999999))
            
            # Send the code via SES
            ses = boto3.client('ses')
            try:
                response = ses.send_email(
                    Source=os.environ['SENDER_EMAIL'],
                    Destination={
                        'ToAddresses': [email]
                    },
                    Message={
                        'Subject': {
                            'Data': 'Your verification code'
                        },
                        'Body': {
                            'Text': {
                                'Data': f'Your verification code is: {code}'
                            }
                        }
                    }
                )
                print(f"Sent verification code to {email}")
            except ClientError as e:
                print(f"Error sending email: {str(e)}")
                raise e
            
            # Store the code in private challenge parameters
            event['response']['privateChallengeParameters'] = {
                'code': code
            }
            
            # Set the public challenge parameters
            event['response']['publicChallengeParameters'] = {
                'message': 'Please check your email for the verification code'
            }
            
            # Set challenge metadata
            event['response']['challengeMetadata'] = 'EMAIL_CODE'
            
        except cognito.exceptions.UserNotFoundException:
            print(f"User not found: {event['userName']}")
            raise Exception("User not found")
        except Exception as e:
            print(f"Error in CreateAuthChallenge: {str(e)}")
            raise e
    
    print("Response:", {
        **event['response'],
        'privateChallengeParameters': '***REDACTED***'  # Don't log the secret code
    })
    return event
