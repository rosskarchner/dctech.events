import os
import json
import uuid
import hashlib
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template, request, redirect, url_for
from flask_cors import CORS
from flask_wtf import FlaskForm
from wtforms import StringField, URLField, DateField, SelectField
from wtforms.validators import DataRequired, URL, Optional, Length
import boto3
from boto3.dynamodb.conditions import Key

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-for-testing')
# Update CORS configuration to allow credentials
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "*"}})

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb', 
                         endpoint_url=os.environ.get('AWS_ENDPOINT_URL', 'http://dynamodb-local:8000'))
events_table = dynamodb.Table(os.environ.get('EVENTS_TABLE', 'LOCAL_EVENTS'))

def get_next_monday():
    """Get the date of the next Monday"""
    today = datetime.today()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7  # If today is Monday, get next Monday
    next_monday = today + timedelta(days=days_until_monday)
    return next_monday.strftime('%Y-%m-%d')

class EventForm(FlaskForm):
    class Meta:
        csrf = False  # Disable CSRF for cross-domain form submission
    
    title = StringField('Event Title', validators=[DataRequired(), Length(min=3, max=100)])
    event_date = DateField('Event Date', format='%Y-%m-%d', validators=[DataRequired()])
    event_hour = SelectField('Hour', choices=[(str(i), str(i)) for i in range(1, 13)], default='6')
    event_minute = SelectField('Minute', choices=[('00', '00'), ('15', '15'), ('30', '30'), ('45', '45')], default='00')
    event_ampm = SelectField('AM/PM', choices=[('AM', 'AM'), ('PM', 'PM')], default='PM')
    location = StringField('Location', validators=[Optional(), Length(max=200)])
    url = URLField('Event URL', validators=[DataRequired(), URL()])

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

@app.route('/')
def hello_world():
    return jsonify({
        "message": "Hello World from authenticated-user-views!",
        "status": "success"
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy"
    })

@app.route('/api/events/suggest-form', methods=['GET'])
def event_suggest_form():
    """Serve the event suggestion form for HTMX inclusion"""
    # Get the base URL from environment or use default
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5001')
    
    # Create form with default values
    form = EventForm()
    form.event_date.data = datetime.strptime(get_next_monday(), '%Y-%m-%d')
    
    return render_template('event_form.html', form=form, api_base_url=api_base_url)

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

# For local development
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)