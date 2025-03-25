import json
import os
import boto3
from botocore.exceptions import ClientError

def lambda_handler(event, context):
    print(os.environ)
    # Initialize AWS clients
    s3 = boto3.client('s3')
    cognito = boto3.client('cognito-idp')
    
    # Get bucket name from environment variable
    bucket = os.environ['BUCKET']
    user_pool_id = os.environ['USER_POOL_ID']
    
    # Get the token from the path parameters
    token = event['pathParameters']['token']
    
    # Check if this is a GET (show form) or POST (process confirmation)
    if event['requestContext']['http']['method'] == 'GET':
        try:
            # Check if token exists in S3
            s3.head_object(Bucket=bucket, Key=f"confirm/{token}")
            
            # Get the email from the object
            response = s3.get_object(Bucket=bucket, Key=f"confirm/{token}")
            email = response['Body'].read().decode('utf-8')
            
            # Return HTML form
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'text/html'
                },
                'body': f'''
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Confirm Newsletter Subscription</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; }}
                        .button {{ background-color: #4CAF50; border: none; color: white; padding: 15px 32px; 
                                 text-align: center; text-decoration: none; display: inline-block; font-size: 16px; 
                                 margin: 4px 2px; cursor: pointer; border-radius: 4px; }}
                    </style>
                </head>
                <body>
                    <h2>Confirm Your Newsletter Subscription</h2>
                    <p>Please confirm that you want to receive DC Tech Events Weekly newsletter at: {email}</p>
                    <form method="POST" action="/confirm/{token}">
                        <input type="hidden" name="email" value="{email}">
                        <button type="submit" class="button">Confirm Subscription</button>
                    </form>
                </body>
                </html>
                '''
            }
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return {
                    'statusCode': 404,
                    'body': 'Invalid or expired confirmation link'
                }
            raise
            
    elif event['requestContext']['http']['method'] == 'POST':
        try:
            # Get the email from S3
            response = s3.get_object(Bucket=bucket, Key=f"confirm/{token}")
            email = response['Body'].read().decode('utf-8')
            
            # Create the user in Cognito
            try:
                response = cognito.admin_create_user(
                    UserPoolId=user_pool_id,
                    Username=email,
                    UserAttributes=[
                        {
                            'Name': 'email',
                            'Value': email
                        },
                        {
                            'Name': 'email_verified',
                            'Value': 'true'
                        },
                        {
                            'Name': 'custom:newsletter',
                            'Value': 'true'
                        }
                    ],
                    MessageAction='SUPPRESS'  # Don't send welcome email
                )
                
                # Delete the confirmation token from S3
                s3.delete_object(Bucket=bucket, Key=f"confirm/{token}")
                
                # Return success page
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'text/html'
                    },
                    'body': '''
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Subscription Confirmed</title>
                        <style>
                            body { font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; }
                        </style>
                    </head>
                    <body>
                        <h2>Thank You!</h2>
                        <p>Your newsletter subscription has been confirmed.</p>
                    </body>
                    </html>
                    '''
                }
                
            except cognito.exceptions.UsernameExistsException:
                # If user exists, update their attributes instead
                cognito.admin_update_user_attributes(
                    UserPoolId=user_pool_id,
                    Username=email,
                    UserAttributes=[
                        {
                            'Name': 'custom:newsletter',
                            'Value': 'true'
                        }
                    ]
                )
                
                # Delete the confirmation token
                s3.delete_object(Bucket=bucket, Key=f"confirm/{token}")
                
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'text/html'
                    },
                    'body': '''
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Subscription Updated</title>
                        <style>
                            body { font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; }
                        </style>
                    </head>
                    <body>
                        <h2>Thank You!</h2>
                        <p>Your newsletter subscription has been updated.</p>
                    </body>
                    </html>
                    '''
                }
                
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return {
                    'statusCode': 404,
                    'body': 'Invalid or expired confirmation link'
                }
            raise

    return {
        'statusCode': 405,
        'body': 'Method not allowed'
    }
