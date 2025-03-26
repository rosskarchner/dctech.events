import json
import os
import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
sources_table = dynamodb.Table(os.environ['TABLE_NAME'])

def handler(event, context):
    try:
        print("Manage sources request received")
        print(f"Event: {json.dumps(event, default=str)}")
        
        # Check if user is admin
        is_admin = False
        if event['requestContext']['authorizer']['jwt']['claims'].get('cognito:groups'):
            groups = event['requestContext']['authorizer']['jwt']['claims']['cognito:groups']
            if isinstance(groups, str):
                is_admin = 'admin' in groups
            else:
                is_admin = 'admin' in groups
        
        if not is_admin:
            return {
                'statusCode': 403,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Unauthorized'})
            }
        
        # Handle different HTTP methods
        http_method = event['requestContext']['http']['method']
        
        if http_method == 'GET':
            # List sources with optional filtering
            query_params = event.get('queryStringParameters', {}) or {}
            status = query_params.get('status', 'submitted')
            
            print(f"Listing sources with status: {status}")
            
            response = sources_table.query(
                IndexName='approval-status-index',
                KeyConditionExpression=Key('approval_status').eq(status)
            )
            
            sources = response.get('Items', [])
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'sources': sources})
            }
            
        elif http_method == 'PUT':
            # Update source approval status
            body = json.loads(event['body'])
            source_id = body.get('id')
            status = body.get('status')
            
            print(f"Updating source {source_id} to status: {status}")
            
            if not source_id or not status:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'Source ID and status are required'})
                }
                
            # Update the source
            sources_table.update_item(
                Key={'id': source_id},
                UpdateExpression='SET approval_status = :status, updated_at = :updated_at',
                ExpressionAttributeValues={
                    ':status': status,
                    ':updated_at': datetime.utcnow().isoformat()
                }
            )
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'message': 'Source updated successfully'})
            }
            
        elif http_method == 'DELETE':
            # Delete a source
            path_params = event.get('pathParameters', {}) or {}
            source_id = path_params.get('id')
            
            print(f"Deleting source: {source_id}")
            
            if not source_id:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'Source ID is required'})
                }
            
            sources_table.delete_item(Key={'id': source_id})
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'message': 'Source deleted successfully'})
            }
            
        else:
            return {
                'statusCode': 405,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Method not allowed'})
            }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error'})
        }
