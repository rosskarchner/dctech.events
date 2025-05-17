from template_utils import prepare_group_for_template, prepare_event_for_template
from queries import (
    get_events, get_approved_groups, get_all_groups, get_pending_groups, 
    get_group_by_id, approve_group, delete_group, set_group_pending, 
    update_group, import_groups_from_csv, export_groups_to_csv, get_site_slug
)

from flask import Flask, jsonify, render_template, request, session, redirect, url_for, Response


from datetime import date, datetime, timedelta
from forms import EventForm, GroupForm, GroupCSVImportForm

import os
import uuid
import hashlib
import boto3
import csv
import io
from boto3.dynamodb.conditions import Key, Attr
from auth import init_auth, login_required, group_required, is_authenticated, current_user

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb', 
                         endpoint_url=os.environ.get('AWS_ENDPOINT_URL', 'http://dynamodb-local:8000'))
events_table = dynamodb.Table(os.environ.get('EVENTS_TABLE', 'LOCAL_EVENTS'))
groups_table = dynamodb.Table(os.environ.get('GROUPS_TABLE', 'LOCAL_GROUPS'))


app = Flask(__name__, template_folder='templates')

# Initialize authentication
init_auth(app)

# Remove base_context as it's no longer needed with template inheritance

@app.route("/")
def homepage():
    # Get approved events for current month and next month
    days = get_events(start_date=None, additional_months=1, status='APPROVED')
    
    return render_template('homepage.html', days=days)


@app.route("/week-of/<int:year>-<int:month>-<int:day>/")
def week_of(year, month, day):
    # Get approved events for the given week
    requested_date=date(year, month, day)
    days = get_events(start_date=requested_date, additional_months=0, status='APPROVED')
    
    return render_template('week_page.html', days=days)

@app.route("/groups/")
def approved_groups_list():
    # Get pagination parameters
    last_key = request.args.get('last_key', None)
    
    # Convert string representation of last key to dict if it exists
    if last_key:
        try:
            import json
            last_key = json.loads(last_key)
        except:
            last_key = None
    
    # Get approved groups with pagination
    approved_groups, next_key = get_approved_groups(last_evaluated_key=last_key, limit=50)
    
    # Convert next key to JSON string for URL parameter if it exists
    next_key_str = None
    if next_key:
        import json
        next_key_str = json.dumps(next_key)
    
    return render_template('approved_groups_list.html', 
                          groups=approved_groups, 
                          next_key=next_key_str,
                          has_next=next_key is not None)



@app.route("/admin/groups/")
def groups_admin_shell():
    return render_template('admin_group_shell.html') 


@app.route("/admin/events/")
def events_admin_shell():
    # When running locally, use local authentication
    if os.environ.get('ENVIRONMENT', 'local') == 'local':
        return render_template('admin_events_shell.html', api_url='http://localhost:5000')
    else:
        # In production, use the configured MODERATOR_API_URL
        api_url = os.environ.get('MODERATOR_API_URL', 'http://localhost:5002')
        return render_template('admin_events_shell.html', api_url=api_url)

@app.route("/events/suggest/")
def events_suggest_shell():
    # When running locally, use local authentication
    if os.environ.get('ENVIRONMENT', 'local') == 'local':
        return render_template('event_suggest_shell.html', api_url='http://localhost:5000')
    else:
        # In production, use the configured AUTH_API_URL
        api_url = os.environ.get('AUTH_API_URL', 'http://localhost:5001')
        return render_template('event_suggest_shell.html', api_url=api_url) 

@app.route("/events/review/")
def events_review_shell():
    """Serve the event review shell page with dynamic API URL"""
    # When running locally, use local authentication
    if os.environ.get('ENVIRONMENT', 'local') == 'local':
        return render_template('events_review_shell.html', api_url='http://localhost:5000')
    else:
        # In production, use the configured MODERATOR_API_URL
        api_url = os.environ.get('MODERATOR_API_URL', 'http://localhost:5002')
        return render_template('events_review_shell.html', api_url=api_url)

@app.route("/group/suggest/")
def groups_suggest_shell():
    # When running locally, use local authentication
    if os.environ.get('ENVIRONMENT', 'local') == 'local':
        return render_template('group_suggest_shell.html', api_url='http://localhost:5000')
    else:
        # In production, use the configured AUTH_API_URL
        api_url = os.environ.get('AUTH_API_URL', 'http://localhost:5001')
        return render_template('group_suggest_shell.html', api_url=api_url) 

@app.route("/groups/manage/")
def groups_manage_shell():
    """Serve the group management shell page with dynamic API URL"""
    # When running locally, use local authentication
    if os.environ.get('ENVIRONMENT', 'local') == 'local':
        return render_template('groups_manage_shell.html', api_url='http://localhost:5000')
    else:
        # In production, use the configured MODERATOR_API_URL
        api_url = os.environ.get('MODERATOR_API_URL', 'http://localhost:5000')
        return render_template('groups_manage_shell.html', api_url=api_url)

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
        
        # Create month slug and event slug for the keys
        monthslug = event_datetime.strftime("%Y-%m")
        eventslug = event_datetime.strftime("%d-%H:%M")
        
        # Generate a unique ID
        unique_id = str(uuid.uuid4())
        
        # Create the DynamoDB item
        item = {
            'month': f"{site_slug}#EventsForMonth{monthslug}",
            'sort': f"{eventslug}#suggested:{unique_id}",
            'id': hashlib.sha256(f"{eventslug}#suggested:{unique_id}".encode()).hexdigest(),
            'title': event_data['title'],
            'startDate': event_datetime.isoformat(),
            'localstartDate': event_datetime.isoformat(),  # Assuming local time for simplicity
            'location': event_data.get('location', ''),
            'url': event_data['url'],
            'status': 'PENDING',  # Suggested events start as pending
            'lastUpdated': datetime.now().isoformat(),
            'submissionDate': datetime.now().isoformat(),
            'date': event_datetime.strftime('%Y-%m-%d')  # Add date field for GSI
        }
        
        # Save to DynamoDB
        events_table.put_item(Item=item)
        return True, item['id']
    except Exception as e:
        print(f"Error saving event to database: {str(e)}")
        return False, str(e)


@app.route('/api/events/suggest-form', methods=['GET'])
@login_required
def event_suggest_form():
    """Serve the event suggestion form for HTMX inclusion"""
    # Get the base URL from environment or use default
    # Create form with default values
    form = EventForm()
    form.event_date.data = datetime.strptime(get_next_monday(), '%Y-%m-%d')
    
    return render_template('event_form.html', form=form)

@app.route('/api/events/submit', methods=['POST'])
@login_required
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

@app.route('/api/events/manage', methods=['GET'])
@login_required
@group_required('localhost-moderators')
def events_manage():
    """Serve the events management page for HTMX inclusion"""
    # Get the base URL from environment or use default
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5002')
    
    # Get month parameter from request, default to current month
    month_param = request.args.get('month', None)
    
    # Parse month parameter if provided
    if month_param:
        try:
            selected_date = datetime.strptime(month_param, '%Y-%m')
        except ValueError:
            selected_date = datetime.now(eastern)
    else:
        selected_date = datetime.now(eastern)
    
    # Calculate previous and next month
    if selected_date.month == 1:
        prev_month = f"{selected_date.year-1}-12"
    else:
        prev_month = f"{selected_date.year}-{selected_date.month-1:02d}"
    
    if selected_date.month == 12:
        next_month = f"{selected_date.year+1}-01"
    else:
        next_month = f"{selected_date.year}-{selected_date.month+1:02d}"
    
    # Format current month for display
    current_month_display = selected_date.strftime('%B %Y')
    
    # Get pending events (all of them)
    pending_events = get_pending_events()
    
    # Get approved events for the selected month
    month_start = datetime(selected_date.year, selected_date.month, 1)
    if selected_date.month == 12:
        month_end = datetime(selected_date.year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = datetime(selected_date.year, selected_date.month + 1, 1) - timedelta(days=1)
    
    # Get events for the selected month
    days = get_events(start_date=month_start.date(), additional_months=0, status='APPROVED')
    
    # Extract approved events from days
    approved_events = []
    for day in days:
        for event in day.get('events', []):
            # Check if the event is from an aggregator
            if 'sort' in event and '#aggregated:' in event['sort']:
                event['from_aggregator'] = True
            else:
                event['from_aggregator'] = False
            approved_events.append(event)
    
    # Check if pending events are from aggregator
    for event in pending_events:
        if 'sort' in event and '#aggregated:' in event['sort']:
            event['from_aggregator'] = True
        else:
            event['from_aggregator'] = False
    
    return render_template('events_manage.html', 
                          pending_events=pending_events,
                          approved_events=approved_events,
                          current_month_display=current_month_display,
                          prev_month=prev_month,
                          next_month=next_month,
                          api_base_url=api_base_url)

@app.route('/api/events/edit-form/<event_id>', methods=['GET'])
@login_required
@group_required('localhost-moderators')
def edit_event_form(event_id):
    """Serve the event edit form for HTMX inclusion"""
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5002')
    
    # Get month and sort from request
    month = request.args.get('month')
    sort = request.args.get('sort')
    
    if not month or not sort:
        return jsonify({
            "success": False,
            "message": "Missing required parameters"
        }), 400
    
    # Get the event from DynamoDB
    events_table = get_events_table()
    response = events_table.get_item(
        Key={
            'month': month,
            'sort': sort
        }
    )
    
    if 'Item' not in response:
        return jsonify({
            "success": False,
            "message": "Event not found"
        }), 404
    
    event = response['Item']
    
    # Check if event is from aggregator
    if '#aggregated:' in sort:
        return jsonify({
            "success": False,
            "message": "Cannot edit events from aggregator"
        }), 403
    
    # Create form with event data
    form = EventForm()
    
    # Parse the start date
    if 'localstartDate' in event:
        start_date = datetime.fromisoformat(event['localstartDate'].replace('Z', '+00:00'))
    elif 'startDate' in event:
        start_date = datetime.fromisoformat(event['startDate'].replace('Z', '+00:00'))
    else:
        return jsonify({
            "success": False,
            "message": "Event missing date information"
        }), 400
    
    # Convert to Eastern time for form
    eastern_date = start_date.astimezone(eastern)
    
    # Set form values
    form.title.data = event.get('title', '')
    form.event_date.data = eastern_date.date()
    form.event_hour.data = str(eastern_date.hour % 12 or 12)  # Convert 24h to 12h format
    form.event_minute.data = eastern_date.strftime('%M')
    form.event_ampm.data = 'AM' if eastern_date.hour < 12 else 'PM'
    form.location.data = event.get('location', '')
    form.url.data = event.get('url', '')
    
    # Format event for template
    formatted_event = {
        'id': event.get('id', ''),
        'title': event.get('title', ''),
        'month': month,
        'sort': sort
    }
    
    return render_template('event_edit_form.html', form=form, event=formatted_event, api_base_url=api_base_url)

@app.route('/api/events/edit/<event_id>', methods=['POST'])
@login_required
@group_required('localhost-moderators')
def edit_event(event_id):
    """Handle event edit form submission"""
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5002')
    
    # Get month and sort from request
    month = request.form.get('month')
    sort = request.form.get('sort')
    
    if not month or not sort:
        return jsonify({
            "success": False,
            "message": "Missing required parameters"
        }), 400
    
    # Check if event is from aggregator
    if '#aggregated:' in sort:
        return jsonify({
            "success": False,
            "message": "Cannot edit events from aggregator"
        }), 403
    
    # Get the event from DynamoDB
    events_table = get_events_table()
    response = events_table.get_item(
        Key={
            'month': month,
            'sort': sort
        }
    )
    
    if 'Item' not in response:
        return jsonify({
            "success": False,
            "message": "Event not found"
        }), 404
    
    event = response['Item']
    
    # Create form and validate
    form = EventForm()
    
    if form.validate_on_submit():
        # Combine date and time fields
        event_time = f"{form.event_hour.data}:{form.event_minute.data} {form.event_ampm.data}"
        formatted_date = form.event_date.data.strftime('%Y-%m-%d')
        
        # Parse the new date and time
        event_datetime_str = f"{formatted_date} {event_time}"
        event_datetime = datetime.strptime(event_datetime_str, '%Y-%m-%d %I:%M %p')
        
        # Update the event in DynamoDB
        events_table.update_item(
            Key={
                'month': month,
                'sort': sort
            },
            UpdateExpression="SET title = :title, startDate = :startDate, localstartDate = :localstartDate, location = :location, url = :url, lastUpdated = :lastUpdated, date = :date",
            ExpressionAttributeValues={
                ':title': form.title.data,
                ':startDate': event_datetime.isoformat(),
                ':localstartDate': event_datetime.isoformat(),
                ':location': form.location.data,
                ':url': form.url.data,
                ':lastUpdated': datetime.now().isoformat(),
                ':date': formatted_date
            }
        )
        
        # Get updated events for the page
        return events_manage()
    else:
        # Form validation failed
        # Format event for template
        formatted_event = {
            'id': event.get('id', ''),
            'title': event.get('title', ''),
            'month': month,
            'sort': sort
        }
        
        return render_template('event_edit_form.html', form=form, event=formatted_event, api_base_url=api_base_url, 
                              message="Form validation failed", message_type="error")

@app.route('/api/events/pending/<event_id>', methods=['POST'])
@login_required
@group_required('localhost-moderators')
def set_event_pending(event_id):
    """Set an event to pending status"""
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5002')
    
    # Get month and sort from request
    month = request.form.get('month')
    sort = request.form.get('sort')
    
    if not month or not sort:
        return jsonify({
            "success": False,
            "message": "Missing required parameters"
        }), 400
    
    # Check if event is from aggregator
    if '#aggregated:' in sort:
        return jsonify({
            "success": False,
            "message": "Cannot modify events from aggregator"
        }), 403
    
    try:
        # Update the event in DynamoDB
        events_table = get_events_table()
        events_table.update_item(
            Key={
                'month': month,
                'sort': sort
            },
            UpdateExpression="SET #status = :status, #lastUpdated = :lastUpdated",
            ExpressionAttributeNames={
                '#status': 'status',
                '#lastUpdated': 'lastUpdated'
            },
            ExpressionAttributeValues={
                ':status': 'PENDING',
                ':lastUpdated': datetime.now().isoformat()
            }
        )
        
        # Get updated events for the page
        return events_manage()
    except Exception as e:
        print(f"Error setting event to pending: {str(e)}")
        return events_manage()

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
        
        # Initialize the events table
        events_table = get_events_table()
        
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
            if 'localstartDate' in event:
                start_date = datetime.fromisoformat(event['localstartDate'].replace('Z', '+00:00'))
            elif 'startDate' in event:
                start_date = datetime.fromisoformat(event['startDate'].replace('Z', '+00:00'))
            else:
                continue
            
            # Convert to Eastern time for display
            eastern_date = start_date.astimezone(eastern)
            
            formatted_events.append({
                'id': event.get('id', ''),
                'title': event.get('title', ''),
                'date': eastern_date.strftime('%Y-%m-%d'),
                'time': eastern_date.strftime('%I:%M %p'),
                'location': event.get('location', ''),
                'url': event.get('url', ''),
                'group': event.get('groupName', ''),
                'month': event.get('month', ''),
                'sort': event.get('sort', '')
            })
        
        return formatted_events
    except Exception as e:
        print(f"Error getting pending events: {str(e)}")
        return []

def approve_event(event_id, month, sort):
    """Approve an event by changing its status to APPROVED"""
    try:
        # Update the event in DynamoDB
        events_table.update_item(
            Key={
                'month': month,
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

def delete_event(event_id, month, sort):
    """Delete an event from DynamoDB"""
    try:
        # Delete the event from DynamoDB
        events_table.delete_item(
            Key={
                'month': month,
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
@login_required
@group_required('localhost-moderators')
def events_review():
    """Serve the event review page for HTMX inclusion"""
    # Get the base URL from environment or use default
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5002')
    
    # Get pending events
    events = get_pending_events()
    
    # Return just the HTML fragment needed for the event management UI
    return render_template('events_review_fragment.html', events=events, api_base_url=api_base_url)

@app.route('/api/events/approve/<event_id>', methods=['POST'])
@login_required
@group_required('localhost-moderators')
def approve_event_route(event_id):
    """Approve an event"""
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5002')
    
    # Get month and sort from request
    month = request.form.get('month')
    sort = request.form.get('sort')
    
    if not month or not sort:
        return jsonify({
            "success": False,
            "message": "Missing required parameters"
        }), 400
    
    success, message = approve_event(event_id, month, sort)
    
    if success:
        # Get updated events for the page
        return events_manage()
    else:
        # Return with error message
        return events_manage()

@app.route('/api/events/delete/<event_id>', methods=['POST'])
@login_required
@group_required('localhost-moderators')
def delete_event_route(event_id):
    """Delete an event"""
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5002')
    
    # Get month and sort from request
    month = request.form.get('month')
    sort = request.form.get('sort')
    
    if not month or not sort:
        return jsonify({
            "success": False,
            "message": "Missing required parameters"
        }), 400
    
    # Check if event is from aggregator
    if '#aggregated:' in sort:
        return jsonify({
            "success": False,
            "message": "Cannot delete events from aggregator"
        }), 403
    
    success, message = delete_event(event_id, month, sort)
    
    if success:
        # Get updated events for the page
        return events_manage()
    else:
        # Return with error message
        return events_manage()


@app.route('/api/groups/manage', methods=['GET'])
@login_required
@group_required('localhost-moderators')
def groups_manage():
    """Serve the group management page for HTMX inclusion"""
    # Get the base URL from environment or use default
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
    
    # Get all pending and approved groups (pagination is handled automatically in the query functions)
    pending_groups, _ = get_pending_groups(limit=100)
    approved_groups, _ = get_approved_groups(limit=100)
    
    # Combine groups for display
    groups = pending_groups + approved_groups
    
    return render_template('groups_manage.html', 
                          groups=groups, 
                          api_base_url=api_base_url)

@app.route('/api/groups/import-form', methods=['GET'])
@login_required
@group_required('localhost-moderators')
def groups_import_form():
    """Serve the group import form for HTMX inclusion"""
    # Get the base URL from environment or use default
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
    
    # Create form
    form = GroupCSVImportForm()
    
    return render_template('group_import_form.html', form=form, api_base_url=api_base_url)

@app.route('/api/groups/import', methods=['POST'])
@login_required
@group_required('localhost-moderators')
def groups_import():
    """Handle group import from CSV"""
    # Get the base URL from environment or use default
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
    
    # Check if file was uploaded
    if 'csv_file' not in request.files:
        return render_template('group_import_result.html', 
                              success=False, 
                              message="No file uploaded", 
                              api_base_url=api_base_url)
    
    file = request.files['csv_file']
    
    # Check if file is empty
    if file.filename == '':
        return render_template('group_import_result.html', 
                              success=False, 
                              message="No file selected", 
                              api_base_url=api_base_url)
    
    # Check if file is a CSV
    if not file.filename.endswith('.csv'):
        return render_template('group_import_result.html', 
                              success=False, 
                              message="File must be a CSV", 
                              api_base_url=api_base_url)
    
    # Read the file
    csv_data = file.read().decode('utf-8')
    
    # Import the groups
    success, message, count = import_groups_from_csv(csv_data)
    
    return render_template('group_import_result.html', 
                          success=success, 
                          message=message, 
                          count=count, 
                          api_base_url=api_base_url)

@app.route('/api/groups/approve/<group_id>', methods=['POST'])
@login_required
@group_required('localhost-moderators')
def approve_group_route(group_id):
    """Approve a group"""
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
    
    # Get the site slug
    site_slug = get_site_slug()
    
    # Check if the group_id already has the site slug prefix
    if group_id.startswith(f"{site_slug}!"):
        # Group ID already has the correct prefix, use it as is
        full_group_id = group_id
    else:
        # Clean up the group_id if it contains a domain part
        if '!' in group_id:
            # Extract just the UUID part after the !
            group_id = group_id.split('!')[-1]
        
        # Add the site slug prefix
        full_group_id = f"{site_slug}!{group_id}"
    
    success, message = approve_group(full_group_id)
    
    # Get all pending and approved groups
    pending_groups, _ = get_pending_groups(limit=100)
    approved_groups, _ = get_approved_groups(limit=100)
    
    # Combine groups for display
    groups = pending_groups + approved_groups
    
    if success:
        return render_template('groups_manage.html', 
                              groups=groups, 
                              api_base_url=api_base_url, 
                              message=message, 
                              message_type="success")
    else:
        return render_template('groups_manage.html', 
                              groups=groups, 
                              api_base_url=api_base_url, 
                              message=f"Error: {message}", 
                              message_type="error")

@app.route('/api/groups/delete/<group_id>', methods=['POST'])
@login_required
@group_required('localhost-moderators')
def delete_group_route(group_id):
    """Delete a group"""
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
    
    # Get the site slug
    site_slug = get_site_slug()
    
    # Check if the group_id already has the site slug prefix
    if group_id.startswith(f"{site_slug}!"):
        # Group ID already has the correct prefix, use it as is
        full_group_id = group_id
    else:
        # Clean up the group_id if it contains a domain part
        if '!' in group_id:
            # Extract just the UUID part after the !
            group_id = group_id.split('!')[-1]
        
        # Add the site slug prefix
        full_group_id = f"{site_slug}!{group_id}"
    
    success, message = delete_group(full_group_id)
    
    # Get all pending and approved groups
    pending_groups, _ = get_pending_groups(limit=100)
    approved_groups, _ = get_approved_groups(limit=100)
    
    # Combine groups for display
    groups = pending_groups + approved_groups
    
    if success:
        return render_template('groups_manage.html', 
                              groups=groups, 
                              api_base_url=api_base_url, 
                              message=message, 
                              message_type="success")
    else:
        return render_template('groups_manage.html', 
                              groups=groups, 
                              api_base_url=api_base_url, 
                              message=f"Error: {message}", 
                              message_type="error")

@app.route('/api/groups/pending/<group_id>', methods=['POST'])
@login_required
@group_required('localhost-moderators')
def set_group_pending_route(group_id):
    """Set a group to pending status"""
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
    
    # Get the site slug
    site_slug = get_site_slug()
    
    # Check if the group_id already has the site slug prefix
    if group_id.startswith(f"{site_slug}!"):
        # Group ID already has the correct prefix, use it as is
        full_group_id = group_id
    else:
        # Clean up the group_id if it contains a domain part
        if '!' in group_id:
            # Extract just the UUID part after the !
            group_id = group_id.split('!')[-1]
        
        # Add the site slug prefix
        full_group_id = f"{site_slug}!{group_id}"
    
    success, message = set_group_pending(full_group_id)
    
    # Get all pending and approved groups
    pending_groups, _ = get_pending_groups(limit=100)
    approved_groups, _ = get_approved_groups(limit=100)
    
    # Combine groups for display
    groups = pending_groups + approved_groups
    
    if success:
        return render_template('groups_manage.html', 
                              groups=groups, 
                              api_base_url=api_base_url, 
                              message=message, 
                              message_type="success")
    else:
        return render_template('groups_manage.html', 
                              groups=groups, 
                              api_base_url=api_base_url, 
                              message=f"Error: {message}", 
                              message_type="error")

@app.route('/api/groups/suggest-form', methods=['GET'])
@login_required
def group_suggest_form():
    """Serve the group suggestion form for HTMX inclusion"""
    # Create form with default values
    form = GroupForm()
    
    return render_template('group_form.html', form=form)

@app.route('/api/groups/submit', methods=['POST'])
@login_required
def submit_group():
    """Handle group submission"""
    form = GroupForm()
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5001')
    
    if form.validate_on_submit():
        # Form is valid, process the data
        group_data = {
            'name': form.name.data,
            'website': form.website.data,
            'ical': form.ical.data,
            'fallback_url': form.fallback_url.data,
            'status': 'PENDING'  # New groups start as pending
        }
        
        # Save to database (you would need to implement this function)
        success, result = save_group_to_db(group_data)
        if success:
            group_data['id'] = result
            group_data['saved'] = True
        else:
            group_data['saved'] = False
            group_data['error'] = result
        
        # Return a response suitable for HTMX
        return render_template('group_submit_success.html', group=group_data, api_base_url=api_base_url)
    else:
        # Form has validation errors, redisplay with error messages
        return render_template('group_form.html', form=form, api_base_url=api_base_url)

def save_group_to_db(group_data):
    """Save group data to DynamoDB"""
    try:
        # Get SITEURL from environment or use default
        site_url = os.environ.get('SITEURL', 'http://localhost:5000')
        # Remove trailing slash if present
        if site_url.endswith('/'):
            site_url = site_url[:-1]
        # Create a site slug for the ID prefix
        site_slug = site_url.replace('http://', '').replace('https://', '').replace(':', '_').replace('/', '_')
        
        # Generate a unique ID with site prefix
        unique_id = f"{site_slug}!{str(uuid.uuid4())}"
        
        # Create the DynamoDB item
        item = {
            'id': unique_id,
            'name': group_data['name'],
            'website': group_data['website'],
            'ical': group_data.get('ical', ''),
            'fallback_url': group_data.get('fallback_url', ''),
            'approval_status': f"{site_slug}!PENDING",  # Namespaced approval status
            'active': True,
            'lastUpdated': datetime.now().isoformat(),
            'submissionDate': datetime.now().isoformat()
        }
        
        # Save to DynamoDB
        groups_table.put_item(Item=item)
        return True, item['id']
    except Exception as e:
        print(f"Error saving group to database: {str(e)}")
        return False, str(e)

@app.route('/api/groups/edit-form/<group_id>', methods=['GET'])
@login_required
@group_required('localhost-moderators')
def edit_group_form(group_id):
    """Serve the group edit form for HTMX inclusion"""
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
    
    # Get the group
    group = get_group_by_id(group_id)
    
    if not group:
        return jsonify({
            "success": False,
            "message": "Group not found"
        }), 404
    
    # Create form with group data
    form = GroupForm()
    form.name.data = group.get('name', '')
    form.website.data = group.get('website', '')
    form.ical.data = group.get('ical', '')
    form.fallback_url.data = group.get('fallback_url', '')
    
    return render_template('group_edit_form.html', form=form, group=group, api_base_url=api_base_url)
@app.route('/api/groups/export-csv', methods=['GET'])
@login_required
@group_required('localhost-moderators')
def export_groups_csv():
    """Export groups as CSV file"""
    # Get CSV data
    csv_data = export_groups_to_csv()
    
    # Create response with CSV data
    response = Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=groups.csv"}
    )
    
    return response

@app.route('/api/groups/edit/<group_id>', methods=['POST'])
@login_required
@group_required('localhost-moderators')
def edit_group(group_id):
    """Handle group edit form submission"""
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
    
    # Get the group
    group = get_group_by_id(group_id)
    
    if not group:
        return jsonify({
            "success": False,
            "message": "Group not found"
        }), 404
    
    # Create form and validate
    form = GroupForm()
    
    if form.validate_on_submit():
        # Update group data
        group_data = {
            'name': form.name.data,
            'website': form.website.data,
            'ical': form.ical.data,
            'fallback_url': form.fallback_url.data
        }
        
        # Update the group
        success, message = update_group(group_id, group_data)
        
        # Get pagination parameters from the request
        pending_last_key = request.form.get('pending_last_key', None)
        approved_last_key = request.form.get('approved_last_key', None)
        
        # Convert string representation of last keys to dict if they exist
        if pending_last_key:
            try:
                import json
                pending_last_key = json.loads(pending_last_key)
            except:
                pending_last_key = None
                
        if approved_last_key:
            try:
                import json
                approved_last_key = json.loads(approved_last_key)
            except:
                approved_last_key = None
        
        # Get pending and approved groups with pagination
        pending_groups, pending_next_key = get_pending_groups(last_evaluated_key=pending_last_key, limit=25)
        approved_groups, approved_next_key = get_approved_groups(last_evaluated_key=approved_last_key, limit=25)
        
        # Convert next keys to JSON strings for URL parameters if they exist
        pending_next_key_str = None
        approved_next_key_str = None
        
        if pending_next_key:
            import json
            pending_next_key_str = json.dumps(pending_next_key)
            
        if approved_next_key:
            import json
            approved_next_key_str = json.dumps(approved_next_key)
        
        # Combine groups for display
        groups = pending_groups + approved_groups
        
        if success:
            return render_template('groups_manage.html', 
                                  groups=groups, 
                                  api_base_url=api_base_url, 
                                  message=message, 
                                  message_type="success",
                                  pending_next_key=pending_next_key_str,
                                  approved_next_key=approved_next_key_str,
                                  has_pending_next=pending_next_key is not None,
                                  has_approved_next=approved_next_key is not None)
        else:
            # Return to edit form with error
            return render_template('group_edit_form.html', form=form, group=group, api_base_url=api_base_url, 
                                  message=f"Error: {message}", message_type="error")
    else:
        # Form validation failed
        return render_template('group_edit_form.html', form=form, group=group, api_base_url=api_base_url, 
                              message="Form validation failed", message_type="error")


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)