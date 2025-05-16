from template_utils import prepare_group_for_template, prepare_event_for_template
from queries import get_events, get_approved_groups

from flask import Flask, jsonify, render_template, request


from datetime import date, datetime, timedelta
from forms import EventForm

import os
import uuid
import hashlib
import boto3
from boto3.dynamodb.conditions import Key, Attr

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb', 
                         endpoint_url=os.environ.get('AWS_ENDPOINT_URL', 'http://dynamodb-local:8000'))
events_table = dynamodb.Table(os.environ.get('EVENTS_TABLE', 'LOCAL_EVENTS'))


app = Flask(__name__, template_folder='templates')

base_context = {
    'title': 'DC Tech Events!',
}


@app.route("/")
def homepage():
    # Get approved events for current week and next 3 weeks
    days = get_events(start_date=None, additional_weeks=3, status='APPROVED')
    context = {
                'days': days
              }
    
    return render_template('homepage.html', context=context)


@app.route("/week-of/<int:year>-<int:month>-<int:day>/")
def week_of(year, month, day):
    # Get approved events for the given week
    requested_date=date(year, month, day )
    days = get_events(start_date=requested_date, additional_weeks=0, status='APPROVED')
    context = {
                'days': days
              }

    return render_template('week_page.html', context=context)

@app.route("/groups/")
def approved_groups_list():
    return render_template('approved_groups_list.html', context={'groups': get_approved_groups()})



@app.route("/admin/groups/")
def groups_admin_shell():
    return render_template('admin_group_shell.html') 


@app.route("/admin/events/")
def events_admin_shell():
    return render_template('admin_events_shell.html') 

@app.route("/events/suggest/")
def events_suggest_shell():
    import os
    api_url = os.environ.get('AUTH_API_URL', 'http://localhost:5001')
    return render_template('event_suggest_shell.html', context={'api_url': api_url}) 

@app.route("/events/review/")
def events_review_shell():
    """Serve the event review shell page with dynamic API URL"""
    import os
    api_url = os.environ.get('MODERATOR_API_URL', 'http://localhost:5002')
    return render_template('events_review_shell.html', context={'api_url': api_url})

@app.route("/group/suggest/")
def groups_suggest_shell():
    return render_template('group_suggest_shell.html') 


@app.route("/auth-callback/")
def auth_callback():
    return render_template('auth_callback.html')
    
@app.route("/test/")
def test_jinja():
    return render_template('test/hello.html', title="Test Page", message="Jinja2 is working!")



def get_next_monday():
    """Get the date of the next Monday"""
    today = datetime.today()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7  # If today is Monday, get next Monday
    next_monday = today + timedelta(days=days_until_monday)
    return next_monday.strftime('%Y-%m-%d')



def save_event_to_db(event_data):
    """Save event data to DynamoDB"""
    try:
        # Get SITEURL from environment or use default
        site_url = os.environ.get('SITEURL', 'http://localhost:5000')
        # Remove trailing slash if present
        if site_url.endswith('/'):
            site_url = site_url[:-1]
        # Create a site slug for the partition key prefix
        site_slug = site_url.replace('http://', '').replace('https://', '').replace(':', '_').replace('/', '_')
        
        # Parse the date and time
        event_datetime_str = f"{event_data['event_date']} {event_data['event_time']}"
        event_datetime = datetime.strptime(event_datetime_str, '%Y-%m-%d %I:%M %p')
        
        # Create week slug and event slug for the keys
        weekslug = event_datetime.strftime("%G-W%V")
        eventslug = event_datetime.strftime("%u-%H:%M")
        
        # Generate a unique ID
        unique_id = str(uuid.uuid4())
        
        # Create the DynamoDB item
        item = {
            'week': f"{site_slug}#EventsForWeek{weekslug}",
            'sort': f"{eventslug}#suggested:{unique_id}",
            'id': hashlib.sha256(f"{eventslug}#suggested:{unique_id}".encode()).hexdigest(),
            'title': event_data['title'],
            'startDate': event_datetime.isoformat(),
            'localstartDate': event_datetime.isoformat(),  # Assuming local time for simplicity
            'location': event_data.get('location', ''),
            'url': event_data['url'],
            'status': 'PENDING',  # Suggested events start as pending
            'lastUpdated': datetime.now().isoformat(),
            'submissionDate': datetime.now().isoformat()
        }
        
        # Save to DynamoDB
        events_table.put_item(Item=item)
        return True, item['id']
    except Exception as e:
        print(f"Error saving event to database: {str(e)}")
        return False, str(e)


@app.route('/api/events/suggest-form', methods=['GET'])
def event_suggest_form():
    """Serve the event suggestion form for HTMX inclusion"""
    # Get the base URL from environment or use default
    # Create form with default values
    form = EventForm()
    form.event_date.data = datetime.strptime(get_next_monday(), '%Y-%m-%d')
    
    return render_template('event_form.html', form=form)

@app.route('/api/events/submit', methods=['POST'])
def submit_event():
    """Handle event submission"""
    form = EventForm()
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5001')
    
    # Add debugging information
    print("Form submitted!")
    print(f"Form data: {request.form}")
    print(f"Form errors: {form.errors}")
    
    if form.validate_on_submit():
        print("Form validated successfully!")
        # Combine date and time fields
        event_time = f"{form.event_hour.data}:{form.event_minute.data} {form.event_ampm.data}"
        formatted_date = form.event_date.data.strftime('%Y-%m-%d')
        
        # Form is valid, process the data
        event_data = {
            'title': form.title.data,
            'event_date': formatted_date,
            'event_time': event_time,
            'formatted_datetime': f"{formatted_date} {event_time}",
            'location': form.location.data,
            'url': form.url.data
        }
        
        # Save to database
        success, result = save_event_to_db(event_data)
        if success:
            event_data['id'] = result
            event_data['saved'] = True
        else:
            event_data['saved'] = False
            event_data['error'] = result
        
        # Return a response suitable for HTMX
        return render_template('event_submit_success.html', event=event_data, api_base_url=api_base_url)
    else:
        print(f"Form validation failed: {form.errors}")
        # Form has validation errors, redisplay with error messages
        return render_template('event_form.html', form=form, api_base_url=api_base_url)

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


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)