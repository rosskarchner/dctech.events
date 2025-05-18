from template_utils import prepare_group_for_template, prepare_event_for_template
from queries import (
    get_events, get_approved_groups, get_all_groups, get_pending_groups
)

from flask import Flask, jsonify, render_template, request, session, redirect, url_for, Response
from datetime import date, datetime, timedelta
import os
import boto3
import pytz
from auth import init_auth, login_required, group_required, is_authenticated, current_user

# Import route modules
from events_routes import register_events_routes
from groups_routes import register_groups_routes

# Define Eastern timezone
eastern = pytz.timezone('US/Eastern')

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb', 
                         endpoint_url=os.environ.get('AWS_ENDPOINT_URL', 'http://dynamodb-local:8000'))
events_table = dynamodb.Table(os.environ.get('EVENTS_TABLE', 'LOCAL_EVENTS'))
groups_table = dynamodb.Table(os.environ.get('GROUPS_TABLE', 'LOCAL_GROUPS'))

def get_events_table():
    """Return the events table object"""
    return events_table


app = Flask(__name__, template_folder='templates')

# Initialize authentication
init_auth(app)

# Register API routes
register_events_routes(app, events_table, get_events_table)
register_groups_routes(app, groups_table)

# Remove base_context as it's no longer needed with template inheritance

@app.route("/")
def homepage():
    # Get approved events for current month and next month
    days = get_events(start_date=None, additional_months=1, status='APPROVED')
    
    return render_template('homepage.html', days=days)


@app.route("/<int:year>/<int:month>/")
def month_view(year, month):
    # Get approved events for the given month
    # Create a date object for the first day of the requested month
    requested_date = date(year, month, 1)
    days = get_events(start_date=requested_date, additional_months=0, status='APPROVED')
    
    # Get month name
    month_name = requested_date.strftime('%B')
    
    # Calculate previous and next month
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year
        
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year
    
    return render_template('month_page.html', 
                          days=days, 
                          year=year, 
                          month=month,
                          month_name=month_name,
                          prev_month=prev_month,
                          prev_year=prev_year,
                          next_month=next_month,
                          next_year=next_year)

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
        api_url = os.environ.get('MODERATOR_API_URL', 'http://localhost:5000')
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
        api_url = os.environ.get('MODERATOR_API_URL', 'http://localhost:5000')
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



# Function get_next_monday is now defined in events_routes.py



# Function save_event_to_db is now defined in events_routes.py


# Routes for event_suggest_form and submit_event are now defined in events_routes.py

# Route for events_manage is now defined in events_routes.py

# Route for edit_event_form is now defined in events_routes.py

# Route for edit_event is now defined in events_routes.py

# Route for set_event_pending is now defined in events_routes.py

# Function get_pending_events is now defined in events_routes.py

# Function approve_event is now defined in events_routes.py

# Function delete_event is now defined in events_routes.py

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

# Route for events_review is now defined in events_routes.py

# Route for approve_event_route is now defined in events_routes.py

# Route for delete_event_route is now defined in events_routes.py


# Route for groups_manage is now defined in groups_routes.py

# Route for groups_import_form is now defined in groups_routes.py

# Route for groups_import is now defined in groups_routes.py

# Function _process_group_action is now defined in groups_routes.py

# Route for approve_group_route is now defined in groups_routes.py

# Route for delete_group_route is now defined in groups_routes.py

# Route for set_group_pending_route is now defined in groups_routes.py

# Route for group_suggest_form is now defined in groups_routes.py

# Route for submit_group is now defined in groups_routes.py

# Function save_group_to_db is now defined in groups_routes.py

# Route for edit_group_form is now defined in groups_routes.py
# Route for export_groups_csv is now defined in groups_routes.py

# Route for edit_group is now defined in groups_routes.py


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)