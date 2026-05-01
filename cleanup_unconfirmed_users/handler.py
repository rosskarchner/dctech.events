"""
Lambda function to clean up unconfirmed user accounts older than 1 month.

Runs weekly via EventBridge rule. Deletes users from Cognito user pool
that have been unconfirmed for longer than 30 days.
"""

import os
import boto3
from datetime import datetime, timedelta, timezone

cognito = boto3.client('cognito-idp')
USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID')


def lambda_handler(event, context):
    """Remove unconfirmed users older than 1 month."""
    print(f"Starting cleanup of unconfirmed users older than 1 month")
    
    if not USER_POOL_ID:
        print("ERROR: COGNITO_USER_POOL_ID not set")
        return {
            'statusCode': 500,
            'body': 'COGNITO_USER_POOL_ID environment variable not set',
        }
    
    deleted_count = 0
    error_count = 0
    one_month_ago = datetime.now(timezone.utc) - timedelta(days=30)
    
    try:
        # List all users in the user pool
        paginator = cognito.get_paginator('list_users')
        pages = paginator.paginate(UserPoolId=USER_POOL_ID)
        
        for page in pages:
            for user in page.get('Users', []):
                username = user.get('Username')
                user_status = user.get('UserStatus')
                user_create_date = user.get('UserCreateDate')
                
                # Check if user is unconfirmed
                if user_status != 'UNCONFIRMED':
                    continue
                
                # Check if user is older than 1 month
                if user_create_date and user_create_date.replace(tzinfo=timezone.utc) < one_month_ago:
                    try:
                        cognito.admin_delete_user(
                            UserPoolId=USER_POOL_ID,
                            Username=username
                        )
                        print(f"Deleted unconfirmed user: {username} (created {user_create_date})")
                        deleted_count += 1
                    except Exception as e:
                        print(f"ERROR deleting user {username}: {e}")
                        error_count += 1
        
        message = f"Successfully deleted {deleted_count} unconfirmed users. Errors: {error_count}"
        print(message)
        
        return {
            'statusCode': 200,
            'body': message,
        }
    
    except Exception as e:
        print(f"ERROR in cleanup function: {e}")
        return {
            'statusCode': 500,
            'body': f'Error cleaning up users: {str(e)}',
        }
