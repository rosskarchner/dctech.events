import os
import sys
import boto3
import chevron
import logging
from chalice import Chalice, Response
from datetime import datetime, timedelta
import re
from decimal import Decimal
import json


from  dateutil.parser import parse as dateparser

from chalicelib.rendering import render_template

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'INFO')
numeric_level = getattr(logging, log_level.upper(), None)
if not isinstance(numeric_level, int):
    numeric_level = logging.INFO

# Initialize Chalice app with debug mode
app = Chalice(app_name='hypertext', debug=True)
app.log.setLevel(numeric_level)

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
events_table = dynamodb.Table(os.environ.get('EVENTS_TABLE_NAME', 'EventsTable'))

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

@app.route('/')
def index():
    """
    Render the hello world template
    """
    app.log.debug("Entering index route")
    context = {
        'title': 'Hello from Chevron!',
        'message': 'Welcome to your first Chevron template with Chalice.',
        'show_time': True,
        'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    app.log.debug(f"Rendering index template with context: {context}")
    return render_template(app, 'hello.mustache', **context)


@app.route('/week-of/{date_str}')
def week_of(date_str):
    """
    Display events for a specific week
    
    URL format: /week-of/MM-DD-YYYY/
    Example: /week-of/4-1-2025/
    """
    try:
        # Parse the date from the URL
        match = re.match(r'(\d{1,2})-(\d{1,2})-(\d{4})', date_str)
        if not match:
            return Response(
                body="Invalid date format. Use MM-DD-YYYY format.",
                status_code=400,
                headers={'Content-Type': 'text/plain'}
            )
        
        month, day, year = map(int, match.groups())
        target_date = datetime(year, month, day)
        
        # Calculate the ISO week number
        iso_year, iso_week, _ = target_date.isocalendar()
        week_key = f"EventsForWeek{iso_year}-W{iso_week:02d}"

        print(f"Querying for week key: {week_key}")
        app.log.info(f"Querying for week key: {week_key}")
        
        # Query DynamoDB for events in this week
        response = events_table.query(
            KeyConditionExpression="week = :week",
            ExpressionAttributeValues={
                ":week": week_key
            }
        )
        print(f"Query response: {json.dumps(response, cls=DecimalEncoder)}")
        
        # Process events
        events = response.get('Items', [])
        print(f"Found {len(events)} events")
        app.log.info(f"Found {len(events)} events")
        
        # Format events for display
        formatted_events = []
        for event in events:
            print(f"Processing event: {json.dumps(event, cls=DecimalEncoder)}")
            
            # Format the date

            date_obj = dateparser(event["localstartDate"])
            formatted_date = date_obj.strftime("%A, %B %d, %Y")

        
            # Format times
            start_time = event.get('localstartDate')
            end_time = event.get('localendDate', '')
            
            # Check if description exists and has content
            description = event.get('description', '')
            has_description = bool(description.strip()) if description else False
            
            event_data = {
                'title': event.get('title', 'Untitled Event'),
                'formatted_date': formatted_date,
                'start_time': start_time,
                'end_time': end_time,
                'location': event.get('location'),
                'description': description,
                'has_description': has_description,
                'url': event.get('url', ''),
                'source_name': event.get('sourceName', 'Unknown Source')
            }
            
            print(f"Formatted event: {json.dumps(event_data)}")
            formatted_events.append(event_data)
        
        # Calculate previous and next week dates
        prev_date = target_date - timedelta(days=7)
        next_date = target_date + timedelta(days=7)
        
        prev_week = prev_date.strftime("%-m-%-d-%Y")
        next_week = next_date.strftime("%-m-%-d-%Y")
        
        # Prepare context for template
        context = {
            'title': f'Events for Week of {target_date.strftime("%B %d, %Y")}',
            'formatted_date': target_date.strftime("%B %d, %Y"),
            'events': formatted_events,
            'has_events': len(formatted_events) > 0,
            'prev_week': prev_week,
            'next_week': next_week
        }
        
        print(f"Template context: {json.dumps(context, cls=DecimalEncoder)}")
        print(f"Has events: {context['has_events']}")
        print(f"Events count: {len(formatted_events)}")
        
        return render_template(app, 'events_list.mustache', **context)
        
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        app.log.error(f"Error processing request: {str(e)}")
        return Response(
            body=f"Error: {str(e)}",
            status_code=500,
            headers={'Content-Type': 'text/plain'}
        )
