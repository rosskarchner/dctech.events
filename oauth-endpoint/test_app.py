from chalice.test import Client
from app import app, decode_state_parameter
import json
from unittest.mock import patch, MagicMock
import pytest
import os
import base64

@pytest.fixture
def test_client():
    with Client(app) as client:
        yield client

@patch('app.get_github_secret')
@patch('requests.post')
def test_oauth_callback_success(mock_post, mock_secret, test_client):
    """Test successful OAuth callback flow"""
    # Mock the GitHub secret
    mock_secret.return_value = 'test_client_secret'

    # Mock the GitHub token exchange response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'access_token': 'test_access_token_123',
        'token_type': 'bearer'
    }
    mock_post.return_value = mock_response

    response = test_client.http.get('/oauth/callback?code=test_code&state=test_state')

    assert response.status_code == 302
    assert 'Location' in response.headers
    assert 'access_token=test_access_token_123' in response.headers['Location']
    assert 'https://dctech.events/submit/' in response.headers['Location']

    # Verify the request to GitHub was made correctly
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == 'https://github.com/login/oauth/access_token'
    assert call_args[1]['json']['client_id'] == 'Ov23liSTVbSKSvkYW6yg'
    assert call_args[1]['json']['client_secret'] == 'test_client_secret'
    assert call_args[1]['json']['code'] == 'test_code'

def test_oauth_callback_missing_code(test_client):
    """Test OAuth callback with missing code parameter"""
    response = test_client.http.get('/oauth/callback')
    
    assert response.status_code == 302
    assert 'Location' in response.headers
    assert 'error=missing_code' in response.headers['Location']

def test_oauth_callback_error_param(test_client):
    """Test OAuth callback with error parameter"""
    response = test_client.http.get('/oauth/callback?error=access_denied')
    
    assert response.status_code == 302
    assert 'Location' in response.headers
    assert 'error=access_denied' in response.headers['Location']

@patch('app.get_github_secret')
def test_oauth_callback_missing_credentials(mock_secret, test_client):
    """Test OAuth callback when OAuth credentials are not configured"""
    # Mock the GitHub secret to return None
    mock_secret.return_value = None

    response = test_client.http.get('/oauth/callback?code=test_code')

    assert response.status_code == 302
    assert 'error=oauth_not_configured' in response.headers['Location']

@patch('app.get_github_secret')
@patch('requests.post')
def test_oauth_callback_github_error(mock_post, mock_secret, test_client):
    """Test OAuth callback when GitHub returns an error"""
    # Mock the GitHub secret
    mock_secret.return_value = 'test_client_secret'

    mock_response = MagicMock()
    mock_response.json.return_value = {
        'error': 'bad_verification_code',
        'error_description': 'The code passed is incorrect or expired.'
    }
    mock_post.return_value = mock_response

    response = test_client.http.get('/oauth/callback?code=bad_code')

    assert response.status_code == 302
    assert 'error=bad_verification_code' in response.headers['Location']

@patch('app.get_github_secret')
@patch('requests.post')
def test_oauth_callback_no_access_token(mock_post, mock_secret, test_client):
    """Test OAuth callback when no access token is returned"""
    # Mock the GitHub secret
    mock_secret.return_value = 'test_client_secret'

    mock_response = MagicMock()
    mock_response.json.return_value = {}
    mock_post.return_value = mock_response

    response = test_client.http.get('/oauth/callback?code=test_code')

    assert response.status_code == 302
    assert 'error=no_token' in response.headers['Location']

@patch('app.get_github_secret')
@patch('requests.post')
def test_oauth_callback_exception(mock_post, mock_secret, test_client):
    """Test OAuth callback when an exception occurs"""
    # Mock the GitHub secret
    mock_secret.return_value = 'test_client_secret'

    mock_post.side_effect = Exception('Network error')

    response = test_client.http.get('/oauth/callback?code=test_code')

    assert response.status_code == 302
    assert 'error=exchange_failed' in response.headers['Location']

# Tests for state parameter handling

def test_decode_state_parameter_valid_submit():
    """Test decoding valid state parameter for /submit/"""
    state_data = {
        'csrf_token': 'random_token_123',
        'return_url': '/submit/'
    }
    state_json = json.dumps(state_data)
    state_base64 = base64.b64encode(state_json.encode('utf-8')).decode('utf-8')

    result = decode_state_parameter(state_base64)

    assert result is not None
    assert result['csrf_token'] == 'random_token_123'
    assert result['return_url'] == '/submit/'

def test_decode_state_parameter_valid_submit_group():
    """Test decoding valid state parameter for /submit-group/"""
    state_data = {
        'csrf_token': 'random_token_456',
        'return_url': '/submit-group/'
    }
    state_json = json.dumps(state_data)
    state_base64 = base64.b64encode(state_json.encode('utf-8')).decode('utf-8')

    result = decode_state_parameter(state_base64)

    assert result is not None
    assert result['csrf_token'] == 'random_token_456'
    assert result['return_url'] == '/submit-group/'

def test_decode_state_parameter_invalid_base64():
    """Test decoding invalid base64 state parameter"""
    result = decode_state_parameter('not_valid_base64!!!')
    assert result is None

def test_decode_state_parameter_missing():
    """Test decoding missing state parameter"""
    result = decode_state_parameter(None)
    assert result is None

def test_decode_state_parameter_empty():
    """Test decoding empty state parameter"""
    result = decode_state_parameter('')
    assert result is None

def test_decode_state_parameter_not_json():
    """Test decoding state parameter that's not JSON"""
    state_base64 = base64.b64encode(b'not json data').decode('utf-8')
    result = decode_state_parameter(state_base64)
    assert result is None

def test_decode_state_parameter_missing_csrf_token():
    """Test decoding state parameter missing csrf_token"""
    state_data = {
        'return_url': '/submit/'
    }
    state_json = json.dumps(state_data)
    state_base64 = base64.b64encode(state_json.encode('utf-8')).decode('utf-8')

    result = decode_state_parameter(state_base64)
    assert result is None

def test_decode_state_parameter_missing_return_url():
    """Test decoding state parameter missing return_url"""
    state_data = {
        'csrf_token': 'random_token_789'
    }
    state_json = json.dumps(state_data)
    state_base64 = base64.b64encode(state_json.encode('utf-8')).decode('utf-8')

    result = decode_state_parameter(state_base64)
    assert result is None

def test_decode_state_parameter_invalid_return_url():
    """Test decoding state parameter with invalid return_url"""
    state_data = {
        'csrf_token': 'random_token_abc',
        'return_url': '/admin/'  # Not an allowed path
    }
    state_json = json.dumps(state_data)
    state_base64 = base64.b64encode(state_json.encode('utf-8')).decode('utf-8')

    result = decode_state_parameter(state_base64)
    assert result is None

def test_decode_state_parameter_valid_edit():
    """Test decoding valid state parameter for /edit/ path"""
    state_data = {
        'csrf_token': 'random_token_edit',
        'return_url': '/edit/'
    }
    state_json = json.dumps(state_data)
    state_base64 = base64.b64encode(state_json.encode('utf-8')).decode('utf-8')

    result = decode_state_parameter(state_base64)

    assert result is not None
    assert result['csrf_token'] == 'random_token_edit'
    assert result['return_url'] == '/edit/'

def test_decode_state_parameter_valid_edit_with_hash():
    """Test decoding valid state parameter for /edit/event/ with hash fragment"""
    state_data = {
        'csrf_token': 'random_token_hash',
        'return_url': '/edit/event/#abc123'
    }
    state_json = json.dumps(state_data)
    state_base64 = base64.b64encode(state_json.encode('utf-8')).decode('utf-8')

    result = decode_state_parameter(state_base64)

    assert result is not None
    assert result['csrf_token'] == 'random_token_hash'
    assert result['return_url'] == '/edit/event/#abc123'

@patch('app.get_github_secret')
@patch('requests.post')
def test_oauth_callback_with_valid_state_submit(mock_post, mock_secret, test_client):
    """Test OAuth callback with valid state parameter for /submit/"""
    # Mock the GitHub secret
    mock_secret.return_value = 'test_client_secret'

    # Mock the GitHub token exchange response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'access_token': 'test_access_token_123',
        'token_type': 'bearer'
    }
    mock_post.return_value = mock_response

    # Create valid state parameter
    state_data = {
        'csrf_token': 'random_token_123',
        'return_url': '/submit/'
    }
    state_json = json.dumps(state_data)
    state_base64 = base64.b64encode(state_json.encode('utf-8')).decode('utf-8')

    response = test_client.http.get(f'/oauth/callback?code=test_code&state={state_base64}')

    assert response.status_code == 302
    assert 'Location' in response.headers
    assert 'https://dctech.events/submit/' in response.headers['Location']
    assert 'access_token=test_access_token_123' in response.headers['Location']

@patch('app.get_github_secret')
@patch('requests.post')
def test_oauth_callback_with_valid_state_submit_group(mock_post, mock_secret, test_client):
    """Test OAuth callback with valid state parameter for /submit-group/"""
    # Mock the GitHub secret
    mock_secret.return_value = 'test_client_secret'

    # Mock the GitHub token exchange response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'access_token': 'test_access_token_456',
        'token_type': 'bearer'
    }
    mock_post.return_value = mock_response

    # Create valid state parameter
    state_data = {
        'csrf_token': 'random_token_456',
        'return_url': '/submit-group/'
    }
    state_json = json.dumps(state_data)
    state_base64 = base64.b64encode(state_json.encode('utf-8')).decode('utf-8')

    response = test_client.http.get(f'/oauth/callback?code=test_code&state={state_base64}')

    assert response.status_code == 302
    assert 'Location' in response.headers
    assert 'https://dctech.events/submit-group/' in response.headers['Location']
    assert 'access_token=test_access_token_456' in response.headers['Location']

@patch('app.get_github_secret')
def test_oauth_callback_with_invalid_state(mock_secret, test_client):
    """Test OAuth callback with invalid state parameter defaults to /submit/"""
    # Mock the GitHub secret
    mock_secret.return_value = 'test_client_secret'

    response = test_client.http.get('/oauth/callback?code=test_code&state=invalid_state')

    assert response.status_code == 302
    assert 'Location' in response.headers
    # Should default to /submit/ when state is invalid and continue with OAuth flow
    # Since we didn't mock requests.post, it will fail and redirect with error
    assert 'https://dctech.events/submit/' in response.headers['Location']
    assert 'error=' in response.headers['Location']

@patch('app.get_github_secret')
@patch('requests.post')
def test_oauth_callback_error_with_valid_state(mock_post, mock_secret, test_client):
    """Test OAuth callback error redirects to correct return_url from state"""
    # Mock the GitHub secret
    mock_secret.return_value = 'test_client_secret'

    # Mock GitHub returning an error
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'error': 'bad_verification_code'
    }
    mock_post.return_value = mock_response

    # Create valid state parameter for /submit-group/
    state_data = {
        'csrf_token': 'random_token_789',
        'return_url': '/submit-group/'
    }
    state_json = json.dumps(state_data)
    state_base64 = base64.b64encode(state_json.encode('utf-8')).decode('utf-8')

    response = test_client.http.get(f'/oauth/callback?code=bad_code&state={state_base64}')

    assert response.status_code == 302
    assert 'Location' in response.headers
    assert 'https://dctech.events/submit-group/' in response.headers['Location']
    assert 'error=bad_verification_code' in response.headers['Location']