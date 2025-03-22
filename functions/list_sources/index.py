import os
import json
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

def handler(event, context):
    try:
        # Get query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        
        # Initialize scan parameters
        scan_params = {
            'Limit': 50  # Default page size
        }
        
        # Handle pagination using LastEvaluatedKey
        if 'nextToken' in query_params:
            try:
                scan_params['ExclusiveStartKey'] = json.loads(query_params['nextToken'])
            except json.JSONDecodeError:
                return {
                    'statusCode': 400,
                    'body': json.dumps({
                        'error': 'Invalid pagination token'
                    })
                }
        
        # Check if filtering by organization name
        if query_params.get('organization_name'):
            # Use GSI to query by organization name
            response = table.query(
                IndexName='organization-index',
                KeyConditionExpression=Key('organization_name').eq(query_params['organization_name']),
                **scan_params
            )
        else:
            # Perform regular scan
            response = table.scan(**scan_params)
        
        # Prepare the response
        result = {
            'sources': response['Items'],
            'count': len(response['Items']),
            'total': response.get('Count', 0)
        }
        
        # Add pagination token if more results exist
        if 'LastEvaluatedKey' in response:
            result['nextToken'] = json.dumps(response['LastEvaluatedKey'])
        
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
