import os
import json
import boto3
from urllib.parse import urlparse
from datetime import datetime
from botocore.exceptions import ClientError

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
        # Get source ID from path parameters
        source_id = event['pathParameters']['id']
        
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

        # Prepare update expression
        update_expression = """
            SET organization_name = :org_name,
                url = :url,
                ical_url = :ical_url,
                updated_at = :updated_at
        """
        
        expression_values = {
            ':org_name': body['organization_name'],
            ':url': body['url'],
            ':ical_url': body['ical_url'],
            ':updated_at': datetime.utcnow().isoformat()
        }
        
        try:
            # Update the item
            response = table.update_item(
                Key={'id': source_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values,
                ConditionExpression='attribute_exists(id)',  # Ensure item exists
                ReturnValues='ALL_NEW'
            )
            
            return {
                'statusCode': 200,
                'body': json.dumps(response['Attributes'])
            }
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return {
                    'statusCode': 404,
                    'body': json.dumps({
                        'error': 'Source not found'
                    })
                }
            raise
            
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
