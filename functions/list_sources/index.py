import json
import os
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
sources_table = dynamodb.Table(os.environ['TABLE_NAME'])

def handler(event, context):
    try:
        print("List sources request received")
        
        # Only show approved sources
        response = sources_table.query(
            IndexName='approval-status-index',
            KeyConditionExpression=Key('approval_status').eq('approved')
        )
        
        sources = response.get('Items', [])
        
        # Remove internal fields before returning
        for source in sources:
            if 'approval_status' in source:
                del source['approval_status']
            if 'submitted_by' in source:
                del source['submitted_by']
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'sources': sources})
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error'})
        }
