import os
import json
import functools
import requests
import jwt
from flask import request, jsonify, session, redirect, url_for, g
from werkzeug.local import LocalProxy

# Mock user database for local development
MOCK_USERS = {
    "user1": {
        "username": "user1",
        "password": "password1",
        "groups": ["localhost-users"]
    },
    "user2": {
        "username": "user2",
        "password": "password2",
        "groups": ["localhost-users", "localhost-moderators"]
    },
    "admin": {
        "username": "admin",
        "password": "admin",
        "groups": ["localhost-users", "localhost-moderators", "localhost-admins"]
    }
}

def get_current_user():
    """Get the current authenticated user from session"""
    if 'user' in session:
        return session['user']
    return None

# Create a proxy for the current user
current_user = LocalProxy(get_current_user)

def is_authenticated():
    """Check if the current request is authenticated"""
    return 'user' in session

def is_in_group(group_name):
    """Check if the current user is in the specified group"""
    if not is_authenticated():
        return False
    
    user = session.get('user', {})
    user_groups = user.get('groups', [])
    
    # Handle the case where 'moderators' and 'localhost-moderators' are equivalent
    if group_name == 'moderators' and 'localhost-moderators' in user_groups:
        return True
    
    return group_name in user_groups

def login_required(f):
    """Decorator to require authentication for a route"""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # For API routes in production, validate JWT token
        if request.path.startswith('/api/') and os.environ.get('ENVIRONMENT', 'local') != 'local':
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({
                    'error': 'Authentication required',
                    'status': 401
                }), 401
                
            token = auth_header.split(' ')[1]
            try:
                # Validate token with Cognito
                user_info = validate_cognito_token(token)
                if not user_info:
                    return jsonify({
                        'error': 'Invalid token',
                        'status': 401
                    }), 401
                    
                # Store user info in session
                session['user'] = user_info
            except Exception as e:
                return jsonify({
                    'error': f'Authentication error: {str(e)}',
                    'status': 401
                }), 401
        # For regular routes or local development
        elif not is_authenticated():
            if request.path.startswith('/api/'):
                return jsonify({
                    'error': 'Authentication required',
                    'status': 401
                }), 401
            else:
                return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def group_required(group_name):
    """Decorator to require membership in a specific group"""
    def decorator(f):
        @functools.wraps(f)
        @login_required  # First ensure the user is logged in
        def decorated_function(*args, **kwargs):
            if not is_in_group(group_name):
                if request.path.startswith('/api/'):
                    return jsonify({
                        'error': f'Access denied. Membership in {group_name} required',
                        'status': 403
                    }), 403
                else:
                    return jsonify({
                        'error': f'Access denied. Membership in {group_name} required',
                        'status': 403
                    }), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def mock_authenticate(username, password):
    """Mock authentication function for local development"""
    if username in MOCK_USERS and MOCK_USERS[username]['password'] == password:
        user_data = MOCK_USERS[username].copy()
        # Don't include password in the session
        user_data.pop('password', None)
        return user_data
    return None

def validate_cognito_token(token):
    """Validate a JWT token from Cognito"""
    # Only used in production
    if os.environ.get('ENVIRONMENT', 'local') == 'local':
        return None
        
    try:
        # Get Cognito user pool ID and app client ID from environment
        user_pool_id = os.environ.get('COGNITO_USER_POOL_ID')
        app_client_id = os.environ.get('COGNITO_APP_CLIENT_ID')
        
        if not user_pool_id or not app_client_id:
            raise ValueError("Cognito configuration missing")
            
        # Get the JWKs from Cognito
        region = user_pool_id.split('_')[0]
        jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
        jwks_response = requests.get(jwks_url)
        jwks = jwks_response.json()
        
        # Decode the token header to get the key ID
        header = jwt.get_unverified_header(token)
        kid = header['kid']
        
        # Find the key with matching kid
        key = None
        for jwk in jwks['keys']:
            if jwk['kid'] == kid:
                key = jwk
                break
                
        if not key:
            raise ValueError("No matching key found")
            
        # Construct the public key
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
        
        # Verify and decode the token
        decoded = jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            audience=app_client_id,
            options={"verify_exp": True}
        )
        
        # Extract user info
        user_info = {
            'username': decoded.get('username', decoded.get('cognito:username', decoded.get('sub'))),
            'email': decoded.get('email', ''),
            'groups': decoded.get('cognito:groups', [])
        }
        
        return user_info
    except Exception as e:
        print(f"Token validation error: {str(e)}")
        return None

def init_auth(app):
    """Initialize authentication for the Flask app"""
    # Set a secret key for session encryption
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key')
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Handle login requests"""
        # In production, redirect to Cognito hosted UI
        if os.environ.get('ENVIRONMENT', 'local') != 'local':
            cognito_domain = os.environ.get('AUTH_DOMAIN_NAME', 'auth.dctech.events')
            app_client_id = os.environ.get('COGNITO_APP_CLIENT_ID')
            redirect_uri = os.environ.get('SITEURL', 'https://dctech.events') + '/auth-callback/'
            
            # Use implicit grant flow for passwordless authentication
            login_url = f"https://{cognito_domain}/login?client_id={app_client_id}&response_type=token&scope=email+openid+profile&redirect_uri={redirect_uri}"
            return redirect(login_url)
        
        # For local development, use mock authentication
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            user = mock_authenticate(username, password)
            
            if user:
                session['user'] = user
                next_url = request.args.get('next', '/')
                return redirect(next_url)
            else:
                return jsonify({
                    'error': 'Invalid credentials',
                    'status': 401
                }), 401
        
        # Render login form for GET requests in local development
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Login</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    max-width: 400px;
                    margin: 0 auto;
                    padding: 20px;
                }
                .form-group {
                    margin-bottom: 15px;
                }
                label {
                    display: block;
                    margin-bottom: 5px;
                }
                input[type="text"], input[type="password"] {
                    width: 100%;
                    padding: 8px;
                    box-sizing: border-box;
                }
                button {
                    background-color: #4CAF50;
                    color: white;
                    padding: 10px 15px;
                    border: none;
                    cursor: pointer;
                }
                .info {
                    margin-top: 20px;
                    padding: 10px;
                    background-color: #f8f9fa;
                    border-radius: 4px;
                }
            </style>
        </head>
        <body>
            <h1>Login</h1>
            <form method="post">
                <div class="form-group">
                    <label for="username">Username:</label>
                    <input type="text" id="username" name="username" required>
                </div>
                <div class="form-group">
                    <label for="password">Password:</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <button type="submit">Login</button>
            </form>
            <div class="info">
                <h3>Available Test Users:</h3>
                <ul>
                    <li><strong>user1</strong> / password1 - Regular user</li>
                    <li><strong>user2</strong> / password2 - Moderator</li>
                    <li><strong>admin</strong> / admin - Admin</li>
                </ul>
            </div>
        </body>
        </html>
        '''
    
    @app.route('/logout')
    def logout():
        """Handle logout requests"""
        # In production, redirect to Cognito logout endpoint
        if os.environ.get('ENVIRONMENT', 'local') != 'local':
            cognito_domain = os.environ.get('AUTH_DOMAIN_NAME', 'auth.dctech.events')
            app_client_id = os.environ.get('COGNITO_APP_CLIENT_ID')
            logout_uri = os.environ.get('SITEURL', 'https://dctech.events')
            
            logout_url = f"https://{cognito_domain}/logout?client_id={app_client_id}&logout_uri={logout_uri}"
            
            # Clear session
            session.pop('user', None)
            return redirect(logout_url)
        
        # For local development
        session.pop('user', None)
        return redirect('/')
    
    @app.route('/api/auth/user')
    def get_user():
        """Return the current user information"""
        if is_authenticated():
            return jsonify({
                'authenticated': True,
                'user': session['user']
            })
        else:
            return jsonify({
                'authenticated': False
            })