import os
import json
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

def handler(event, context):
    try:
        # Get the JWT claims from the authorizer context
        auth_context = event.get('requestContext', {}).get('authorizer', {})
        claims = auth_context.get('jwt', {}).get('claims', {})
        
        # Check if user is admin
        scope = claims.get('scope', '')
        is_admin = scope.endswith("admin")
        
        if not is_admin:
            return {
                'statusCode': 403,
                'headers': {
                    'Content-Type': 'text/html' if 'HX-Request' in event.get('headers', {}) else 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({'error': 'Permission denied'}) if 'HX-Request' not in event.get('headers', {}) else """
                <div class="error-message">
                    <h3>Permission Denied</h3>
                    <p>You do not have permission to delete sources.</p>
                </div>
                """
            }
        
        # Get source ID from path parameters
        source_id = event.get('pathParameters', {}).get('id')
        if not source_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'text/html' if 'HX-Request' in event.get('headers', {}) else 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({'error': 'Missing source ID'}) if 'HX-Request' not in event.get('headers', {}) else """
                <div class="error-message">
                    <h3>Error</h3>
                    <p>Missing source ID.</p>
                </div>
                """
            }
        
        # Delete the source from DynamoDB
        table.delete_item(Key={'id': source_id})
        
        # Check if this is an HTMX request
        if 'HX-Request' in event.get('headers', {}):
            # Return empty response for HTMX to remove the element
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'text/html',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': '' # Empty body will cause the element to be removed
            }
        else:
            # Return success message for API
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({'message': 'Source deleted successfully'})
            }

    except Exception as e:
        print(f"Error deleting source: {str(e)}")
        
        # Check if this is an HTMX request
        if 'HX-Request' in event.get('headers', {}):
            error_html = """
            <div class="error-message">
                <h3>Error</h3>
                <p>There was a problem deleting the source. Please try again later.</p>
            </div>
            """
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'text/html',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': error_html
            }
        else:
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({'error': str(e)})
            }
