import boto3
import os
import json
import time

# Initialize S3 client
s3 = boto3.client('s3')

# Get environment variables
VERIFICATION_BUCKET_NAME = os.environ.get('VERIFICATION_BUCKET_NAME')

def handler(event, context):
    # Log the event for debugging
    print('Event:', event)
    
    # Extract challenge information
    request = event['request']
    challenge_answer = request.get('challengeAnswer', '')
    
    # Check if we have a verification code stored in S3
    try:
        if VERIFICATION_BUCKET_NAME:
            # Try to get the verification data from S3 using the code as the key
            response = s3.get_object(
                Bucket=VERIFICATION_BUCKET_NAME,
                Key=f"codes/{challenge_answer}.json"
            )
            
            # Parse the stored data
            verification_data = json.loads(response['Body'].read().decode('utf-8'))
            expires_at = verification_data.get('expires_at', 0)
            
            # Check if the code has expired
            if time.time() > expires_at:
                print(f"Code {challenge_answer} has expired")
                event['response'] = {
                    'answerCorrect': False
                }
                return event
            
            print(f"Found valid verification data for code {challenge_answer}")
            event['response'] = {
                'answerCorrect': True
            }
            return event
    except Exception as e:
        print(f"Error retrieving code from S3: {str(e)}")
    
    # Fall back to the code in private challenge parameters
    expected_code = request['privateChallengeParameters'].get('code', '')
    print(f"Falling back to private challenge parameters. Comparing challenge answer '{challenge_answer}' with expected code '{expected_code}'")
    
    if challenge_answer == expected_code:
        event['response'] = {
            'answerCorrect': True
        }
    else:
        event['response'] = {
            'answerCorrect': False
        }
    
    return event
