"""
Cognito JWT authorization.

Reads pre-validated claims from API Gateway Cognito Authorizer context.
API Gateway validates the JWT before invoking Lambda, so re-validation
here is unnecessary.
"""

import os

COGNITO_CLIENT_ID = os.environ.get('COGNITO_USER_POOL_CLIENT_ID', '')


def get_user_from_event(event):
    """
    Extract user claims from the API Gateway Cognito Authorizer context.

    API Gateway validates the JWT before Lambda is invoked; claims are
    injected into event['requestContext']['authorizer']['claims'].

    Returns (claims_dict, error_response) tuple.
    """
    try:
        claims = (
            event.get('requestContext', {})
                 .get('authorizer', {})
                 .get('claims', {})
        )
        if not claims or not claims.get('sub'):
            return None, {'statusCode': 401, 'body': 'Unauthorized'}
        return claims, None
    except Exception:
        return None, {'statusCode': 401, 'body': 'Unauthorized'}


def require_admin(claims):
    """
    Check if user has admin group membership.

    Returns error response dict if not admin, None if authorized.
    """
    groups = claims.get('cognito:groups', [])
    if 'admins' not in groups:
        return {'statusCode': 403, 'body': 'Admin access required'}
    return None
