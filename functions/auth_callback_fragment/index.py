import os
import json

def handler(event, context):
    """
    Returns JavaScript code with the authentication logic using direct token exchange
    """
    # Get environment variables
    user_pool_id = os.environ.get('USER_POOL_ID')
    client_id = os.environ.get('CLIENT_ID')
    region = os.environ.get('REGION', 'us-east-1')
    
    # Create the JavaScript code
    js_code = f"""
    // Configuration with actual values
    const userPoolId = '{user_pool_id}';
    const clientId = '{client_id}';
    const region = '{region}';
    
    // Function to parse URL parameters
    function getUrlParams() {{
        const params = {{}};
        const queryString = window.location.search.substring(1);
        const pairs = queryString.split('&');
        
        for (let i = 0; i < pairs.length; i++) {{
            const pair = pairs[i].split('=');
            params[decodeURIComponent(pair[0])] = decodeURIComponent(pair[1] || '');
        }}
        
        return params;
    }}

    // Function to exchange authorization code for tokens
    async function exchangeCodeForTokens(code) {{
        const redirectUri = 'https://dctech.events/static/callback.html';
        
        // Prepare the token request
        const tokenEndpoint = `https://auth.dctech.events/oauth2/token`;
        const body = new URLSearchParams({{
            grant_type: 'authorization_code',
            client_id: clientId,
            redirect_uri: redirectUri,
            code: code
        }});
        
        // Make the token request
        const response = await fetch(tokenEndpoint, {{
            method: 'POST',
            headers: {{
                'Content-Type': 'application/x-www-form-urlencoded'
            }},
            body: body
        }});
        
        if (!response.ok) {{
            const errorData = await response.json();
            throw new Error(`Token exchange failed: ${{errorData.error_description || errorData.error || response.statusText}}`);
        }}
        
        return await response.json();
    }}

    // Function to parse JWT and get expiration time
    function getTokenExpiration(token) {{
        try {{
            const base64Url = token.split('.')[1];
            const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
            const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {{
                return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
            }}).join(''));
            
            const payload = JSON.parse(jsonPayload);
            return payload.exp;
        }} catch (e) {{
            console.error('Error parsing token:', e);
            // Default to 1 hour from now if parsing fails
            return Math.floor(Date.now() / 1000) + 3600;
        }}
    }}

    // Main function to handle the callback
    async function handleCallback() {{
        try {{
            document.getElementById('status').textContent = 'Processing authentication...';
            
            const params = getUrlParams();
            
            // Check if there's an error in the URL
            if (params.error) {{
                throw new Error(`Authentication error: ${{params.error_description || params.error}}`);
            }}
            
            // Check if there's a code in the URL
            if (!params.code) {{
                throw new Error('No authorization code found in the URL');
            }}
            
            // Exchange the code for tokens
            const tokens = await exchangeCodeForTokens(params.code);
            
            // Store tokens in localStorage
            localStorage.setItem('id_token', tokens.id_token);
            localStorage.setItem('access_token', tokens.access_token);
            localStorage.setItem('refresh_token', tokens.refresh_token);
            
            // Store token expiration time
            const expirationTime = getTokenExpiration(tokens.id_token);
            localStorage.setItem('token_expiration', expirationTime.toString());
            
            // Store user info from the ID token
            const idTokenPayload = JSON.parse(atob(tokens.id_token.split('.')[1]));
            localStorage.setItem('user_email', idTokenPayload.email || '');
            localStorage.setItem('user_name', idTokenPayload.name || '');
            
            document.getElementById('status').textContent = 'Authentication successful! Redirecting...';
            
            // Redirect to the home page or the page the user was trying to access
            setTimeout(() => {{
                const returnTo = localStorage.getItem('auth_return_to') || '/';
                localStorage.removeItem('auth_return_to'); // Clear the stored return URL
                window.location.href = returnTo.startsWith('http') ? returnTo : 'https://dctech.events' + returnTo;
            }}, 1000);
            
        }} catch (error) {{
            console.error('Error in handleCallback:', error);
            document.getElementById('status').textContent = `Authentication failed: ${{error.message}}`;
            document.getElementById('error-details').textContent = error.toString();
            document.getElementById('error-container').style.display = 'block';
        }}
    }}
    
    // Run the callback handler when the page loads
    window.onload = handleCallback;
    """
    
    # Return the JavaScript with appropriate headers
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/javascript',
            'Cache-Control': 'no-cache, no-store, must-revalidate'
        },
        'body': js_code
    }
