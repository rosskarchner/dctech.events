"""
Cognito JWT validation and authorization.

Validates JWT tokens from Cognito, checks group membership for admin routes.
"""

import json
import os
import time

import jwt
import requests

COGNITO_USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID', '')
COGNITO_REGION = os.environ.get('AWS_REGION', 'us-east-1')

_jwks_cache = None
_jwks_cache_time = 0
JWKS_CACHE_TTL = 3600  # 1 hour


def _get_jwks():
    """Fetch and cache Cognito JWKS keys."""
    global _jwks_cache, _jwks_cache_time
    now = time.time()
    if _jwks_cache and (now - _jwks_cache_time) < JWKS_CACHE_TTL:
        return _jwks_cache

    jwks_url = (
        f'https://cognito-idp.{COGNITO_REGION}.amazonaws.com'
        f'/{COGNITO_USER_POOL_ID}/.well-known/jwks.json'
    )
    resp = requests.get(jwks_url, timeout=5)
    resp.raise_for_status()
    _jwks_cache = resp.json()
    _jwks_cache_time = now
    return _jwks_cache


def decode_token(token):
    """
    Decode and validate a Cognito JWT token.

    Returns the decoded claims dict, or None if invalid.
    """
    try:
        headers = jwt.get_unverified_header(token)
        kid = headers.get('kid')
        if not kid:
            return None

        jwks = _get_jwks()
        key_data = None
        for key in jwks.get('keys', []):
            if key['kid'] == kid:
                key_data = key
                break

        if not key_data:
            return None

        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_data))

        issuer = (
            f'https://cognito-idp.{COGNITO_REGION}.amazonaws.com'
            f'/{COGNITO_USER_POOL_ID}'
        )

        claims = jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            issuer=issuer,
            options={'verify_aud': False},
        )
        return claims

    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Exception):
        return None


def get_user_from_event(event):
    """
    Extract and validate user from API Gateway event.

    Returns (claims_dict, error_response) tuple.
    If valid, error_response is None. If invalid, claims is None.
    """
    auth_header = event.get('headers', {}).get('Authorization', '')
    if not auth_header:
        auth_header = event.get('headers', {}).get('authorization', '')

    if not auth_header:
        return None, {'statusCode': 401, 'body': 'Missing Authorization header'}

    token = auth_header
    if token.startswith('Bearer '):
        token = token[7:]

    claims = decode_token(token)
    if not claims:
        return None, {'statusCode': 401, 'body': 'Invalid or expired token'}

    return claims, None


def require_admin(claims):
    """
    Check if user has admin group membership.

    Returns error response dict if not admin, None if authorized.
    """
    groups = claims.get('cognito:groups', [])
    if 'admins' not in groups:
        return {'statusCode': 403, 'body': 'Admin access required'}
    return None
