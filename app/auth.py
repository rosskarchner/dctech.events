import os
import json
import functools
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
        if not is_authenticated():
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

def init_auth(app):
    """Initialize authentication for the Flask app"""
    # Set a secret key for session encryption
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key')
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Handle login requests"""
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            # In production, this would validate against Cognito
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
        
        # Render login form for GET requests
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