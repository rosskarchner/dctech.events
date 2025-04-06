import os

CLIENT_ID = os.environ.get('CLIENT_ID')

def handler(event, context):
    # Get query parameters
    query_params = event.get('queryStringParameters', {}) or {}
    error = query_params.get('error', '')
    redirect = query_params.get('redirect', '/')
    
    # Error messages
    error_messages = {
        'invalid_token': 'Invalid or expired login link. Please try again.',
        'expired_token': 'Your login link has expired. Please request a new one.',
        'server_error': 'An error occurred. Please try again later.'
    }
    
    error_message = error_messages.get(error, '')
    
    # HTML for the login form
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign In - DC Tech Events</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 500px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1 {{
            color: #2c3e50;
        }}
        .form-group {{
            margin-bottom: 15px;
        }}
        label {{
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }}
        input[type="email"] {{
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }}
        button {{
            background-color: #3498db;
            color: white;
            border: none;
            padding: 10px 15px;
            border-radius: 4px;
            cursor: pointer;
        }}
        button:hover {{
            background-color: #2980b9;
        }}
        .error {{
            color: #e74c3c;
            margin-bottom: 15px;
        }}
        .info {{
            background-color: #f8f9fa;
            border-left: 4px solid #3498db;
            padding: 10px 15px;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <h1>Sign In to DC Tech Events</h1>
    
    {f'<div class="error">{error_message}</div>' if error_message else ''}
    
    <form id="loginForm">
        <div class="form-group">
            <label for="email">Email Address</label>
            <input type="email" id="email" name="email" required>
        </div>
        <button type="submit">Send Magic Link</button>
    </form>
    
    <div class="info">
        <p>We'll send you a secure link to sign in. No password needed!</p>
    </div>
    
    <div id="message" style="margin-top: 20px; display: none;"></div>
    
    <script>
        document.getElementById('loginForm').addEventListener('submit', async function(e) {{
            e.preventDefault();
            
            const email = document.getElementById('email').value;
            const messageDiv = document.getElementById('message');
            const submitButton = document.querySelector('button[type="submit"]');
            
            // Disable button and show loading state
            submitButton.disabled = true;
            submitButton.textContent = 'Sending...';
            
            try {{
                const response = await fetch('/api/auth/magic-link', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }},
                    body: JSON.stringify({{ email }})
                }});
                
                const data = await response.json();
                
                if (response.ok) {{
                    messageDiv.style.display = 'block';
                    messageDiv.style.color = 'green';
                    messageDiv.innerHTML = '<p>✅ Check your email for a magic link to sign in!</p>';
                    document.getElementById('loginForm').style.display = 'none';
                }} else {{
                    messageDiv.style.display = 'block';
                    messageDiv.style.color = 'red';
                    messageDiv.textContent = data.message || 'An error occurred. Please try again.';
                }}
            }} catch (error) {{
                messageDiv.style.display = 'block';
                messageDiv.style.color = 'red';
                messageDiv.textContent = 'Network error. Please try again.';
            }} finally {{
                // Reset button state
                submitButton.disabled = false;
                submitButton.textContent = 'Send Magic Link';
            }}
        }});
    </script>
</body>
</html>
    """
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/html'
        },
        'body': html
    }
