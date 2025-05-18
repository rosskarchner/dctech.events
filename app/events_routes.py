from flask import Flask, jsonify, render_template, request, session, redirect, url_for, Response
from datetime import date, datetime, timedelta
from forms import EventForm
import os
import uuid
import hashlib
import pytz
from boto3.dynamodb.conditions import Key, Attr
from auth import login_required, group_required
from queries import get_events

# Define Eastern timezone
eastern = pytz.timezone('US/Eastern')

def register_events_routes(app, events_table, get_events_table):
    """Register all events-related routes with the Flask app"""
    
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
        api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
        
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
        api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
        
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
        api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
        
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
            # Get SITEURL from environment or use default
            site_url = os.environ.get('SITEURL', 'http://localhost:5000')
            # Remove trailing slash if present
            if site_url.endswith('/'):
                site_url = site_url[:-1]
            # Create a site slug for the partition key prefix
            site_slug = site_url.replace('http://', '').replace('https://', '').replace(':', '_').replace('/', '_')
            
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
                    ':status': f"{site_slug}!PENDING",
                    ':lastUpdated': datetime.now().isoformat()
                }
            )
            
            # Get updated events for the page
            return events_manage()
        except Exception as e:
            print(f"Error setting event to pending: {str(e)}")
            return events_manage()

    @app.route('/api/events/review', methods=['GET'])
    @login_required
    @group_required('localhost-moderators')
    def events_review():
        """Serve the event review page for HTMX inclusion"""
        # Get the base URL from environment or use default
        api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
        
        # Get pending events
        events = get_pending_events()
        
        # Return just the HTML fragment needed for the event management UI
        return render_template('events_review_fragment.html', events=events, api_base_url=api_base_url)

    @app.route('/api/events/approve/<event_id>', methods=['POST'])
    @login_required
    @group_required('localhost-moderators')
    def approve_event_route(event_id):
        """Approve an event"""
        api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
        
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
        api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
        
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
                'status': f"{site_slug}!PENDING",  # Namespace the status with site slug
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
                FilterExpression=Attr('status').eq(f"{site_slug}!PENDING")
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
            # Get SITEURL from environment or use default
            site_url = os.environ.get('SITEURL', 'http://localhost:5000')
            # Remove trailing slash if present
            if site_url.endswith('/'):
                site_url = site_url[:-1]
            # Create a site slug for the partition key prefix
            site_slug = site_url.replace('http://', '').replace('https://', '').replace(':', '_').replace('/', '_')
            
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
                    ':status': f"{site_slug}!APPROVED",
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