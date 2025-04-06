def handler(event, context):
    # Log the event for debugging
    print('Event:', event)
    
    # Extract challenge information from the event
    request = event['request']
    session = request['session']
    
    # Initialize the response
    response = {}
    
    # If this is a new auth session, present the custom challenge
    if len(session) == 0:
        response = {
            'challengeName': 'CUSTOM_CHALLENGE',
            'issueTokens': False,
            'failAuthentication': False
        }
    
    # If the user has successfully completed the challenge
    elif session[-1]['challengeName'] == 'CUSTOM_CHALLENGE' and session[-1]['challengeResult'] == True:
        # This means the user successfully completed the magic link verification
        response = {
            'challengeName': None,
            'issueTokens': True,
            'failAuthentication': False
        }
    
    # If the user has failed the challenge
    else:
        response = {
            'challengeName': 'CUSTOM_CHALLENGE',
            'issueTokens': False,
            'failAuthentication': True
        }
    
    # Return the response
    event['response'] = response
    return event
