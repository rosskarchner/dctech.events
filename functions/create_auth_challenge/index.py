import os
import boto3
import random
import string
import urllib.parse

def handler(event, context):
    # Log the event for debugging
    print('Event:', event)
    
    # Extract user information
    request = event['request']
    
    # Get the username/email
    username = None
    if 'userAttributes' in request and 'email' in request['userAttributes']:
        username = request['userAttributes']['email']
    elif 'userName' in request:
        username = request['userName']
    
    # Get the user's sub ID
    user_sub = None
    if 'userAttributes' in request and 'sub' in request['userAttributes']:
        user_sub = request['userAttributes']['sub']
    
    # If we still don't have a username or sub, log an error
    if not username:
        print("Warning: Could not find username in the request")
        username = "user@example.com"  # Fallback for debugging
    
    if not user_sub:
        print("Warning: Could not find user sub ID in the request")
        user_sub = "unknown-user"  # Fallback for debugging
    
    # Check if this is a new challenge or a retry
    is_new_challenge = True
    if 'session' in request and len(request['session']) > 0:
        for session in request['session']:
            if session.get('challengeName') == 'CUSTOM_CHALLENGE':
                is_new_challenge = False
                break
    
    # If this is a retry, use the existing code from the previous challenge
    code = None
    if not is_new_challenge and 'session' in request and len(request['session']) > 0:
        for session in request['session']:
            if 'privateChallengeParameters' in session and 'code' in session['privateChallengeParameters']:
                code = session['privateChallengeParameters']['code']
                break
    
    # If no existing code or this is a new challenge, generate a new code
    # But only if we don't have a code from a previous challenge
    if not code:
        # Check if there's a code in the current request's private challenge parameters
        # This would be set by the magic_link_handler
        if 'privateChallengeParameters' in request and 'code' in request['privateChallengeParameters']:
            code = request['privateChallengeParameters']['code']
        else:
            # Generate a new code only if we don't have one from anywhere else
            code = ''.join(random.choices(string.digits, k=6))
    
    # Store the code in the private challenge parameters
    # This is securely stored by Cognito and passed to verify function
    event['response'] = {
        'privateChallengeParameters': {
            'code': code,
            'sub': user_sub
        },
        'publicChallengeParameters': {
            'email': username
        },
        'challengeMetadata': 'CUSTOM_CHALLENGE'
    }
    
    return event
