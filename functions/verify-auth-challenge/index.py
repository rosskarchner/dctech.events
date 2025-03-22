import json
import boto3
import os

def handler(event, context):
    print("Event:", event)  # Helpful for debugging
    
    if event['triggerSource'] == 'VerifyAuthChallengeResponse_Authentication':
        # Get the expected code from private challenge parameters
        expected_code = event['request']['privateChallengeParameters']['code']
        
        # Get the code provided by the user
        provided_code = event['request']['challengeAnswer']
        
        # Verify the code
        event['response']['answerCorrect'] = (expected_code == provided_code)
        
        if event['response']['answerCorrect']:
            print(f"Correct code provided for user: {event['userName']}")
            # If the code is correct, mark the email as verified
            try:
                cognito = boto3.client('cognito-idp')
                cognito.admin_update_user_attributes(
                    UserPoolId=os.environ['USER_POOL_ID'],
                    Username=event['userName'],
                    UserAttributes=[
                        {
                            'Name': 'email_verified',
                            'Value': 'true'
                        }
                    ]
                )
                print(f"Updated email_verified status for user: {event['userName']}")
            except Exception as e:
                print(f"Error updating email_verified status: {str(e)}")
                # Don't fail the authentication if this update fails
                pass
        else:
            print(f"Incorrect code provided for user: {event['userName']}")
    
    print("Response:", event['response'])
    return event
