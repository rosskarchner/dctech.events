import os
import json
import boto3
from boto3.dynamodb.conditions import Key

# AWS Clients
dynamodb = boto3.resource('dynamodb')
ses = boto3.client('ses')

# Configuration
CONFIG_TABLE = os.environ.get('CONFIG_TABLE_NAME', 'dctech-events')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'ross@karchner.com')
SENDER_EMAIL = 'noreply@dctech.events'

def get_pending_count():
    """Query the config table for pending drafts."""
    table = dynamodb.Table(CONFIG_TABLE)
    try:
        response = table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq('STATUS#pending'),
            Select='COUNT'
        )
        return response.get('Count', 0)
    except Exception as e:
        print(f"Error querying DynamoDB: {e}")
        return 0

def send_notification(count):
    """Send an email via SES."""
    subject = f"Action Required: {count} pending submission(s) on DC Tech Events"
    body = f"Hello Ross,\n\nThere are {count} items in the moderation queue awaiting review.\n\nManage them here: https://manage.dctech.events/queue.html\n\n- DC Tech Events Bot"
    
    try:
        ses.send_email(
            Source=SENDER_EMAIL,
            Destination={'ToAddresses': [ADMIN_EMAIL]},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body}}
            }
        )
        print(f"Notification sent to {ADMIN_EMAIL}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def lambda_handler(event, context):
    """AWS Lambda entry point."""
    print("Checking for pending submissions...")
    count = get_pending_count()
    
    if count > 0:
        print(f"Found {count} pending items. Sending notification...")
        success = send_notification(count)
        return {
            'statusCode': 200,
            'body': json.dumps({'sent': success, 'count': count})
        }
    else:
        print("No pending items found.")
        return {
            'statusCode': 200,
            'body': json.dumps({'sent': False, 'count': 0})
        }
