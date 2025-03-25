import json
import base64
import urllib.parse
import re
import os
import secrets
import hashlib

import boto3
from botocore.exceptions import ClientError



def is_valid_email(email):
    # Regular expression for email validation
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def send_email(recipient, subject, body_text, body_html=None):
    ses = boto3.client('ses')
    sender = os.environ['SENDER_EMAIL']
    
    email_message = {
        'Source': sender,
        'Destination': {
            'ToAddresses': [recipient]
        },
        'Message': {
            'Subject': {
                'Data': subject,
                'Charset': 'UTF-8'
            },
            'Body': {
                'Text': {
                    'Data': body_text,
                    'Charset': 'UTF-8'
                }
            }
        }
    }
    
    # Add HTML body if provided
    if body_html:
        email_message['Message']['Body']['Html'] = {
            'Data': body_html,
            'Charset': 'UTF-8'
        }
    
    try:
        response = ses.send_email(**email_message)
        return True
    except ClientError as e:
        print(f"Error sending email: {str(e)}")
        return False


def save_to_s3(bucket, key, data):
    s3 = boto3.client('s3')
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=data)
        return True
    except ClientError as e:
        print(f"Error saving to S3: {str(e)}")
        return False

def check_s3_key_exists(bucket_name, key):
    """
    Check if a key exists in an S3 bucket
    
    Args:
        bucket_name (str): Name of the S3 bucket
        key (str): The key to check
    
    Returns:
        bool: True if key exists, False if it doesn't
    """
    s3 = boto3.client('s3')
    try:
        s3.head_object(Bucket=bucket_name, Key=key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        # If there's a different error (like permissions), raise it
        raise

def lambda_handler(event, context):
    userpool_id = os.environ.get('USERPOOL_ID')
    cognito = boto3.client('cognito-idp')

    bucket_name=os.environ.get('BUCKET')
    # Handle POST request (form data)
    if event.get('body'):
        # Check content type to determine how to parse the body
        content_type = event.get('headers', {}).get('content-type', '')
        
        try:
            if 'application/x-www-form-urlencoded' in content_type:
                # Parse form data (e.g., from standard HTML form submission)
                if event.get('isBase64Encoded', False):
                    body = base64.b64decode(event['body']).decode('utf-8')
                else:
                    body = event['body']
                form_data = dict(urllib.parse.parse_qsl(body))
                
                # Validate email
                email = form_data.get('email')
                if not email:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({
                            'message': 'Email address is required'
                        })
                    }
                
                if not is_valid_email(email):
                    return {
                        'statusCode': 400,
                        'body': json.dumps({
                            'message': 'Invalid email address format'
                        })
                    }
                


            
            elif 'application/json' in content_type:
                # Parse JSON data
                body = json.loads(event['body'])
                
                # Validate email
                email = body.get('email')
                if not email:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({
                            'message': 'Email address is required'
                        })
                    }
                
                if not is_valid_email(email):
                    return {
                        'statusCode': 400,
                        'body': json.dumps({
                            'message': 'Invalid email address format'
                        })
                    }
                
                
        except Exception as e:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'message': f'Error processing request: {str(e)}'
                })
            }


    email_hash = hashlib.sha256(email.encode('utf-8')).hexdigest()

    if not check_s3_key_exists(bucket_name, "seen/" + email_hash):
        confirmation_token = "confirm/" + secrets.token_urlsafe(16)
        save_to_s3(bucket_name,confirmation_token,email)
        save_to_s3(bucket_name, "seen/" + email_hash, email)
        confirm_url = f"https://dctech.events/{confirmation_token}"
        send_email(email, "Confirm your DC Tech Events subscription", f"Please confirm your email address by clicking on the following link:\n\n{confirm_url}")

    
    return {
          "isBase64Encoded": False,
          "statusCode": 302,
          "headers": {
               "Location": "https://dctech.events/thanks.html"
          },
          "multiValueHeaders": {},
          "body": ""
     }
