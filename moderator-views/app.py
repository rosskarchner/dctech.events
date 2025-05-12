import os
import json
from datetime import datetime
from flask import Flask, jsonify, render_template, request, redirect, url_for
from flask_cors import CORS
import boto3
from boto3.dynamodb.conditions import Key, Attr

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-for-testing')
# Update CORS configuration to allow credentials
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "*"}})

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb', 
                         endpoint_url=os.environ.get('AWS_ENDPOINT_URL', 'http://dynamodb-local:8000'))
events_table = dynamodb.Table(os.environ.get('EVENTS_TABLE', 'LOCAL_EVENTS'))

def get_pending_events():
    """Get all events with status=PENDING"""
    try:
        # Get SITEURL from environment or use default
        site_url = os.environ.get('SITEURL', 'http://localhost:5000')
        # Remove trailing slash if present
        if site_url.endswith('/'):
            site_url = site_url[:-1]
        # Create a site slug for the partition key prefix
        site_slug = site_url.replace('http://', '').replace('https://', '').replace(':', '_').replace('/', '_')
        
        # We need to scan the table since we're filtering on a non-key attribute (status)
        # In a production environment, we might want to use a GSI for this
        response = events_table.scan(
            FilterExpression=Attr('status').eq('PENDING')
        )
        
        events = response.get('Items', [])
        
        # Format events for display
        formatted_events = []
        for event in events:
            # Parse the start date
            start_date = datetime.fromisoformat(event.get('startDate', ''))
            
            formatted_events.append({
                'id': event.get('id', ''),
                'title': event.get('title', ''),
                'formatted_date': start_date.strftime('%Y-%m-%d'),
                'formatted_time': start_date.strftime('%I:%M %p'),
                'location': event.get('location', ''),
                'url': event.get('url', ''),
                'submission_date': datetime.fromisoformat(event.get('submissionDate', '')).strftime('%Y-%m-%d %H:%M'),
                'week': event.get('week', ''),
                'sort': event.get('sort', '')
            })
        
        return formatted_events
    except Exception as e:
        print(f"Error getting pending events: {str(e)}")
        return []

def approve_event(event_id, week, sort):
    """Approve an event by changing its status to APPROVED"""
    try:
        # Update the event in DynamoDB
        events_table.update_item(
            Key={
                'week': week,
                'sort': sort
            },
            UpdateExpression="SET #status = :status, #lastUpdated = :lastUpdated",
            ExpressionAttributeNames={
                '#status': 'status',
                '#lastUpdated': 'lastUpdated'
            },
            ExpressionAttributeValues={
                ':status': 'APPROVED',
                ':lastUpdated': datetime.now().isoformat()
            }
        )
        return True, "Event approved successfully"
    except Exception as e:
        print(f"Error approving event: {str(e)}")
        return False, str(e)

def delete_event(event_id, week, sort):
    """Delete an event from DynamoDB"""
    try:
        # Delete the event from DynamoDB
        events_table.delete_item(
            Key={
                'week': week,
                'sort': sort
            }
        )
        return True, "Event deleted successfully"
    except Exception as e:
        print(f"Error deleting event: {str(e)}")
        return False, str(e)

@app.route('/')
def hello_world():
    return jsonify({
        "message": "Hello World from moderator-views!",
        "status": "success"
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy"
    })

@app.route('/api/events/review', methods=['GET'])
def events_review():
    """Serve the event review page for HTMX inclusion"""
    # Get the base URL from environment or use default
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5002')
    
    # Get pending events
    events = get_pending_events()
    
    return render_template('events_review.html', events=events, api_base_url=api_base_url)

@app.route('/api/events/approve/<event_id>', methods=['POST'])
def approve_event_route(event_id):
    """Approve an event"""
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5002')
    
    # Get week and sort from request
    week = request.form.get('week')
    sort = request.form.get('sort')
    
    if not week or not sort:
        return jsonify({
            "success": False,
            "message": "Missing required parameters"
        }), 400
    
    success, message = approve_event(event_id, week, sort)
    
    if success:
        # Get updated list of pending events
        events = get_pending_events()
        return render_template('events_review.html', events=events, api_base_url=api_base_url, 
                              message=message, message_type="success")
    else:
        # Get current list of pending events
        events = get_pending_events()
        return render_template('events_review.html', events=events, api_base_url=api_base_url, 
                              message=f"Error: {message}", message_type="error")

@app.route('/api/events/delete/<event_id>', methods=['POST'])
def delete_event_route(event_id):
    """Delete an event"""
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5002')
    
    # Get week and sort from request
    week = request.form.get('week')
    sort = request.form.get('sort')
    
    if not week or not sort:
        return jsonify({
            "success": False,
            "message": "Missing required parameters"
        }), 400
    
    success, message = delete_event(event_id, week, sort)
    
    if success:
        # Get updated list of pending events
        events = get_pending_events()
        return render_template('events_review.html', events=events, api_base_url=api_base_url, 
                              message=message, message_type="success")
    else:
        # Get current list of pending events
        events = get_pending_events()
        return render_template('events_review.html', events=events, api_base_url=api_base_url, 
                              message=f"Error: {message}", message_type="error")

# For local development
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)