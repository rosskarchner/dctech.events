def handler(event, context):
    # Clear all authentication cookies
    cookies = [
        "id_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Secure; HttpOnly; SameSite=Lax",
        "access_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Secure; HttpOnly; SameSite=Lax",
        "refresh_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Secure; HttpOnly; SameSite=Lax"
    ]
    
    # Get redirect URL from query parameters or default to home
    query_params = event.get('queryStringParameters', {}) or {}
    redirect_url = query_params.get('redirect', '/')
    
    # Return redirect response with cookies cleared
    return {
        'statusCode': 302,
        'headers': {
            'Location': redirect_url,
            'Set-Cookie': cookies
        },
        'body': ''
    }
