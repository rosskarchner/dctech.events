import json
import os

def handler(event, context):
    # Get the client ID from environment variable
    client_id = os.environ.get('CLIENT_ID')
    
    # Create the complete login form HTML with the correct client ID
    login_form_html = f'''
<!DOCTYPE html>
<html>
<head>
    <title>Passwordless Login</title>
    <style>
        .container {{
            max-width: 400px;
            margin: 40px auto;
            padding: 20px;
            font-family: Arial, sans-serif;
        }}
        .form-group {{
            margin-bottom: 15px;
        }}
        .form-group label {{
            display: block;
            margin-bottom: 5px;
        }}
        .form-group input {{
            width: 100%;
            padding: 8px;
            box-sizing: border-box;
        }}
        .error {{
            color: red;
            margin-bottom: 10px;
        }}
        button {{
            padding: 10px 15px;
            background-color: #007bff;
            color: white;
            border: none;
            cursor: pointer;
        }}
        button:disabled {{
            background-color: #cccccc;
        }}
        #codeForm {{
            display: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Sign In</h2>
        <div id="errorMessage" class="error"></div>

        <form id="emailForm">
            <div class="form-group">
                <label for="email">Email:</label>
                <input type="email" id="email" required>
            </div>
            <button type="submit" id="sendCodeButton">Send Code</button>
        </form>

        <form id="codeForm">
            <div class="form-group">
                <label for="code">Enter verification code:</label>
                <input type="text" id="code" required>
            </div>
            <button type="submit" id="verifyButton">Verify Code</button>
        </form>
    </div>

    <script src="https://sdk.amazonaws.com/js/aws-sdk-2.1001.0.min.js"></script>
    <script>
        // Configuration
        const CLIENT_ID = '{client_id}';
        const REGION = 'us-east-1';

        // Initialize AWS SDK
        AWS.config.region = REGION;
        const cognito = new AWS.CognitoIdentityServiceProvider();

        let sessionToken = null;
        let userEmail = null;

        // Get DOM elements
        const emailForm = document.getElementById('emailForm');
        const codeForm = document.getElementById('codeForm');
        const errorMessage = document.getElementById('errorMessage');
        const sendCodeButton = document.getElementById('sendCodeButton');
        const verifyButton = document.getElementById('verifyButton');

        // Function to check if token is expired
        function isTokenExpired(token) {{
            if (!token) return true;
            
            try {{
                // JWT tokens consist of three parts: header.payload.signature
                const payload = token.split('.')[1];
                // Decode the base64 payload
                const decodedPayload = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
                
                // Check if the token has expired
                const currentTime = Math.floor(Date.now() / 1000);
                return decodedPayload.exp < currentTime;
            }} catch (error) {{
                console.error('Error parsing token:', error);
                return true; // If we can't parse the token, consider it expired
            }}
        }}

        // Handle email form submission
        emailForm.addEventListener('submit', async function(e) {{
            e.preventDefault();
            errorMessage.textContent = '';
            sendCodeButton.disabled = true;
            userEmail = document.getElementById('email').value;

            try {{
                const params = {{
                    AuthFlow: 'CUSTOM_AUTH',
                    ClientId: CLIENT_ID,
                    AuthParameters: {{
                        'USERNAME': userEmail
                    }}
                }};

                const response = await cognito.initiateAuth(params).promise();
                sessionToken = response.Session;
                
                // Show code input form
                emailForm.style.display = 'none';
                codeForm.style.display = 'block';
            }} catch (err) {{
                errorMessage.textContent = err.message;
                console.error('Error:', err);
            }} finally {{
                sendCodeButton.disabled = false;
            }}
        }});

        // Handle verification code form submission
        codeForm.addEventListener('submit', async function(e) {{
            e.preventDefault();
            errorMessage.textContent = '';
            verifyButton.disabled = true;

            try {{
                const code = document.getElementById('code').value;
                const params = {{
                    ChallengeName: 'CUSTOM_CHALLENGE',
                    ClientId: CLIENT_ID,
                    ChallengeResponses: {{
                        'USERNAME': userEmail,
                        'ANSWER': code
                    }},
                    Session: sessionToken
                }};

                const response = await cognito.respondToAuthChallenge(params).promise();
                
                if (response.AuthenticationResult) {{
                    // Store tokens directly (they're already in JWT format)
                    localStorage.setItem('authToken', response.AuthenticationResult.AccessToken);
                    localStorage.setItem('idToken', response.AuthenticationResult.IdToken);
                    
                    if (response.AuthenticationResult.RefreshToken) {{
                        localStorage.setItem('refreshToken', response.AuthenticationResult.RefreshToken);
                    }}

                    console.log('Login successful, tokens stored');
                    window.location.href = '/';
                }}
            }} catch (err) {{
                errorMessage.textContent = err.message;
                console.error('Error:', err);
            }} finally {{
                verifyButton.disabled = false;
            }}
        }});

        // Function to handle token refresh
        async function refreshToken() {{
            const refresh_token = localStorage.getItem('refreshToken');
            if (!refresh_token) {{
                throw new Error('No refresh token available');
            }}

            try {{
                const params = {{
                    AuthFlow: 'REFRESH_TOKEN_AUTH',
                    ClientId: CLIENT_ID,
                    AuthParameters: {{
                        'REFRESH_TOKEN': refresh_token
                    }}
                }};

                const response = await cognito.initiateAuth(params).promise();
                
                if (response.AuthenticationResult) {{
                    // Update stored tokens
                    localStorage.setItem('authToken', response.AuthenticationResult.AccessToken);
                    if (response.AuthenticationResult.IdToken) {{
                        localStorage.setItem('idToken', response.AuthenticationResult.IdToken);
                    }}
                    
                    return response.AuthenticationResult.AccessToken;
                }} else {{
                    throw new Error('Failed to refresh token');
                }}
            }} catch (error) {{
                console.error('Token refresh failed:', error);
                // Clear all tokens and redirect to login
                logout();
                throw error;
            }}
        }}

        // Function to handle logout
        function logout() {{
            localStorage.removeItem('authToken');
            localStorage.removeItem('idToken');
            localStorage.removeItem('refreshToken');
            window.location.href = '/login';
        }}

        // Check if we're already logged in
        document.addEventListener('DOMContentLoaded', function() {{
            const token = localStorage.getItem('authToken');
            
            if (token) {{
                if (isTokenExpired(token)) {{
                    console.log('Token is expired, removing from storage');
                    // Token is expired, remove it and stay on login page
                    localStorage.removeItem('authToken');
                    localStorage.removeItem('idToken');
                    localStorage.removeItem('refreshToken');
                    errorMessage.textContent = 'Your session has expired. Please log in again.';
                }} else {{
                    // Token is valid, redirect to home page
                    window.location.href = '/';
                }}
            }}
        }});
    </script>
</body>
</html>
'''
    
    # Return the HTML with appropriate headers
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/html',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET'
        },
        'body': login_form_html
    }
