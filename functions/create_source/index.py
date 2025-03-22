import os
import json
import uuid
import boto3
from urllib.parse import urlparse
from datetime import datetime, UTC

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

def validate_urls(url, ical_url):
    """Validate both URLs are properly formatted"""
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return False
        result = urlparse(ical_url)
        if not all([result.scheme, result.netloc]):
            return False
        return True
    except:
        return False

def handler(event, context):
    try:
        # Parse the incoming JSON body
        body = json.loads(event['body'])
        
        # Validate required fields
        required_fields = ['organization_name', 'url', 'ical_url']
        if not all(field in body for field in required_fields):
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing required fields. Need organization_name, url, and ical_url'
                })
            }
        
        # Validate URLs
        if not validate_urls(body['url'], body['ical_url']):
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Invalid URL format'
                })
            }

        # Create item
        source_item = {
            'id': str(uuid.uuid4()),
            'organization_name': body['organization_name'],
            'url': body['url'],
            'ical_url': body['ical_url'],
            'created_at': datetime.now(UTC).isoformat(),
            'updated_at': datetime.now(UTC).isoformat()
        }
        
        # Save to DynamoDB
        table.put_item(Item=source_item)
        
        return {
            'statusCode': 201,
            'body': json.dumps(source_item)
        }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
