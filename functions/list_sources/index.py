import json
import os
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
sources_table = dynamodb.Table(os.environ['TABLE_NAME'])

def handler(event, context):
    try:
        print("List sources request received")
        
        # Check if HTML format is requested
        headers = event.get('headers', {})
        accept_header = headers.get('accept', '')
        hx_request = headers.get('hx-request', 'false').lower() == 'true'
        
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
        
        # If HTML is requested or this is an HTMX request, return HTML
        if 'text/html' in accept_header or hx_request:
            html = generate_html_response(sources)
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'text/html'},
                'body': html
            }
        else:
            # Otherwise return JSON
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'sources': sources})
            }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        if 'text/html' in accept_header or hx_request:
            error_html = '<div class="error-message">Error loading sources. Please try again.</div>'
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'text/html'},
                'body': error_html
            }
        else:
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Internal server error'})
            }

def generate_html_response(sources):
    """Generate HTML snippet for sources list"""
    if not sources:
        return '<p>No sources found.</p>'
    
    html = '<div class="sources-grid">'
    
    for source in sources:
        name = source.get('organization_name', 'Unknown Organization')
        website = source.get('url', '#')
        ical_url = source.get('ical_url', '#')
        
        html += f"""
            <div class="source-card">
                <h3>{name}</h3>
                <p>
                    <a href="{website}" target="_blank">Visit Website</a> | 
                    <a href="{ical_url}" target="_blank" title="iCal Feed">📅 Calendar</a>
                </p>
            </div>
        """
    
    html += '</div>'
    return html
