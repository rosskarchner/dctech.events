import os
import json
import boto3
import urllib.parse
import base64

# Initialize AWS clients
cognito = boto3.client('cognito-idp')

# Get environment variables
USER_POOL_ID = os.environ.get('USER_POOL_ID')
CLIENT_ID = os.environ.get('CLIENT_ID')

def handler(event, context):
    try:
        print("Login handler request received")
        print(f"Event: {json.dumps(event, default=str)}")
        
        # Check if this is a GET or POST request
        http_method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')
        
        if http_method == 'GET':
            # Render login form
            return render_login_form(event)
        elif http_method == 'POST':
            # Process login submission
            return process_login(event)
        else:
            return {
                'statusCode': 405,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Method not allowed'})
            }
    except Exception as e:
        print(f"Error in login handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Internal server error: {str(e)}'})
        }

def render_login_form(event):
    """Render the login form HTML"""
    # Get the redirect URL from query parameters
    query_params = event.get('queryStringParameters', {}) or {}
    redirect_url = query_params.get('redirect', '/')
    
    # Check for error message
    error_message = query_params.get('error', '')
    error_html = f"""
        <div class="error-message">
            <p>{error_message}</p>
        </div>
    """ if error_message else ""
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Login - DC Tech Events</title>
        <link rel="stylesheet" href="/static/css/main.css">
        <style>
            .container {{
                max-width: 400px;
                margin: 0 auto;
                padding: 20px;
            }}
            .form-group {{
                margin-bottom: 20px;
            }}
            label {{
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
            }}
            input {{
                width: 100%;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }}
            button {{
                background-color: #007bff;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                cursor: pointer;
                width: 100%;
            }}
            .error-message {{
                background-color: #f8d7da;
                color: #721c24;
                padding: 15px;
                border-radius: 4px;
                margin-bottom: 20px;
            }}
            .signup-link {{
                text-align: center;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Login</h1>
            
            {error_html}
            
            <form action="/login" method="post">
                <div class="form-group">
                    <label for="email">Email:</label>
                    <input type="email" id="email" name="email" required>
                </div>
                
                <input type="hidden" name="redirect" value="{redirect_url}">
                
                <button type="submit">Continue with Email</button>
            </form>
            
            <div class="signup-link">
                <p>Don't have an account? <a href="/signup?redirect={urllib.parse.quote(redirect_url)}">Sign up</a></p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/html',
        },
        'body': html
    }

def process_login(event):
    """Process login form submission"""
    try:
        # Parse form data
        body = event.get('body', '')
        is_base64_encoded = event.get('isBase64Encoded', False)
        
        if is_base64_encoded:
            body = base64.b64decode(body).decode('utf-8')
        
        # Parse form data
        form_data = {}
        for field in body.split('&'):
            if '=' in field:
                key, value = field.split('=', 1)
                form_data[urllib.parse.unquote(key)] = urllib.parse.unquote(value)
        
        email = form_data.get('email', '')
        redirect_url = form_data.get('redirect', '/')
        
        if not email:
            return {
                'statusCode': 302,
                'headers': {
                    'Location': f'/login?error=Email+is+required&redirect={urllib.parse.quote(redirect_url)}'
                }
            }
        
        # Check if user exists in Cognito
        try:
            user_response = cognito.admin_get_user(
                UserPoolId=USER_POOL_ID,
                Username=email
            )
            user_exists = True
        except cognito.exceptions.UserNotFoundException:
            user_exists = False
        
        # If user doesn't exist, redirect to signup
        if not user_exists:
            return {
                'statusCode': 302,
                'headers': {
                    'Location': f'/signup?error=User+not+found.+Please+sign+up+first&email={urllib.parse.quote(email)}&redirect={urllib.parse.quote(redirect_url)}'
                }
            }
        
        # Initiate the custom auth flow
        cognito.admin_initiate_auth(
            UserPoolId=USER_POOL_ID,
            ClientId=CLIENT_ID,
            AuthFlow='CUSTOM_AUTH',
            AuthParameters={
                'USERNAME': email
            }
        )
        
        # Render the "check your email" page
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Check Your Email - DC Tech Events</title>
            <link rel="stylesheet" href="/static/css/main.css">
            <style>
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    text-align: center;
                }}
                .email-icon {{
                    font-size: 48px;
                    margin-bottom: 20px;
                }}
                .back-link {{
                    margin-top: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="email-icon">📧</div>
                <h1>Check Your Email</h1>
                <p>We've sent a login link to <strong>{email}</strong>.</p>
                <p>Click the link in the email to log in to your account.</p>
                <p>The link will expire in 15 minutes.</p>
                <div class="back-link">
                    <a href="/login">Back to Login</a>
                </div>
            </div>
        </body>
        </html>
        """
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html',
            },
            'body': html
        }
            
    except Exception as e:
        print(f"Error processing login: {str(e)}")
        return {
            'statusCode': 302,
            'headers': {
                'Location': '/login?error=An+error+occurred+during+login'
            }
        }
