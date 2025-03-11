import json
import base64
import urllib.parse
import re
import os
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




def lambda_handler(event, context):
    userpool_id = os.environ.get('USERPOOL_ID')
    cognito = boto3.client('cognito-idp')
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
                
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Form data received',
                        'data': form_data
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
                
                

                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'JSON data received',
                        'data': body
                    })
                }
                
        except Exception as e:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'message': f'Error processing request: {str(e)}'
                })
            }
    
    return {
        'statusCode': 400,
        'body': json.dumps({
            'message': 'No data received'
        })
    }
