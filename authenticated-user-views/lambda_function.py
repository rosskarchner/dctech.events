import awsgi
import json
from app import app

def handler(event, context):
    # Ensure event has all required fields for awsgi
    if 'queryStringParameters' not in event:
        event['queryStringParameters'] = None
    if 'pathParameters' not in event:
        event['pathParameters'] = None
    if 'body' not in event:
        event['body'] = None
    
    # Get the response from awsgi
    response = awsgi.response(app, event, context)
    
    # If the response is already in the format API Gateway expects, return it
    if isinstance(response, dict) and 'statusCode' in response:
        return response
    
    # Otherwise, manually format it for API Gateway
    try:
        # Try to parse the response body as JSON
        if isinstance(response[0], bytes):
            body_str = response[0].decode('utf-8')
        else:
            body_str = response[0]
        
        return {
            "statusCode": response[1],
            "headers": dict(response[2]),
            "body": body_str,
            "isBase64Encoded": False
        }
    except Exception as e:
        # If anything goes wrong, return a simple error response
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
            "isBase64Encoded": False
        }