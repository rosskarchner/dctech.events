import os
import json

def handler(event, context):
    try:
        # Log the entire event for debugging
        print("Full event:", json.dumps(event, indent=2))
        
        # Get the JWT claims from the authorizer context
        auth_context = event.get('requestContext', {}).get('authorizer', {})
        print("Auth context:", json.dumps(auth_context, indent=2))
        
        claims = auth_context.get('jwt', {}).get('claims', {})
        print("Claims:", json.dumps(claims, indent=2))
        
        # Get groups from claims
        cognito_groups = claims.get('cognito:groups', '')
        print("Cognito groups:", cognito_groups)
        
        if isinstance(cognito_groups, str):
            if ',' in cognito_groups:
                groups = [g.strip() for g in cognito_groups.split(',')]
            elif cognito_groups:
                groups = [cognito_groups]
            else:
                groups = []
        else:
            groups = []
        

        # Check group membership
        scope = claims.get('scope', '')
        is_admin = scope.endswith("admin")
        is_editor = scope.endswith("editor")

        permissions = {
            "canCreateSources": is_admin,
            "canEditSources": is_admin,
            "canDeleteSources": is_admin,
            "canApproveEvents": is_admin or is_editor,
            "canEditEvents": is_admin or is_editor,
            "canDeleteEvents": is_admin or is_editor,
            "canSubmitEvents": True,
            "canUpdateOwnEvents": True,
            "groups": groups,
            "isAdmin": is_admin,
            "isEditor": is_editor
        }

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': 'https://dctech.events',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Api-Key',
                'Access-Control-Allow-Methods': 'OPTIONS,GET',
                'Access-Control-Allow-Credentials': 'true'
            },
            'body': json.dumps(permissions)
        }

    except Exception as e:
        print(f"Error checking permissions: {str(e)}")
        print(f"Event that caused error: {json.dumps(event, indent=2)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': 'https://dctech.events',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Api-Key',
                'Access-Control-Allow-Methods': 'OPTIONS,GET',
                'Access-Control-Allow-Credentials': 'true'
            },
            'body': json.dumps({
                'error': 'Failed to check permissions',
                'message': str(e)
            })
        }
