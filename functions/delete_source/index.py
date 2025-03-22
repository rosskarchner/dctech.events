import os
import json
import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

def handler(event, context):
    try:
        # Get source ID from path parameters
        source_id = event['pathParameters']['id']
        
        # Try to delete the item
        try:
            response = table.delete_item(
                Key={'id': source_id},
                ConditionExpression='attribute_exists(id)'  # Ensure item exists
            )
            
            return {
                'statusCode': 204,
                'body': ''
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
