import json
import os
import boto3
import logging
from datetime import datetime, timedelta
import pathlib
import time
import pytz
import uuid
import csv
import io
from template_utils import prepare_group_for_template, prepare_event_for_template, sanitize_text
from boto3.dynamodb.conditions import Key, Attr

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize S3 client
s3 = boto3.client('s3')
# Initialize CloudFront client
cloudfront = boto3.client('cloudfront')
# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb', endpoint_url=os.environ.get('AWS_ENDPOINT_URL', 'http://dynamodb-local:8000'))
# Initialize timezone
eastern = pytz.timezone('US/Eastern')

# Set up pretty printing for JSON logs
def pretty_json(obj):
    return json.dumps(obj, indent=2, default=str)

def get_site_slug():
    """
    Get the site slug for the current environment.
    
    Returns:
        Site slug string
    """
    # Get SITEURL from environment or use default
    site_url = os.environ.get('SITEURL', 'http://localhost:5000')
    # Remove trailing slash if present
    if site_url.endswith('/'):
        site_url = site_url[:-1]
    # Create a site slug for filtering by ID prefix
    return site_url.replace('http://', '').replace('https://', '').replace(':', '_').replace('/', '_')

def get_groups_table():
    """
    Get the DynamoDB groups table.
    
    Returns:
        DynamoDB Table resource
    """
    groups_table_name = os.environ.get('GROUPS_TABLE', 'LOCAL_GROUPS')
    return dynamodb.Table(groups_table_name)

def get_events_table():
    """
    Get the DynamoDB events table.
    
    Returns:
        DynamoDB Table resource
    """
    events_table_name = os.environ.get('EVENTS_TABLE', 'LOCAL_EVENTS')
    return dynamodb.Table(events_table_name)

def get_approved_groups(last_evaluated_key=None, limit=50):
    """
    Queries the DynamoDB table for approved groups.
    
    Args:
        last_evaluated_key: The LastEvaluatedKey from the previous query for pagination
        limit: Maximum number of items to return
        
    Returns:
        Tuple of (list of approved groups, LastEvaluatedKey for pagination)
    """
    try:
        # Initialize the groups table
        groups_table = get_groups_table()
        
        # Get site slug
        site_slug = get_site_slug()
        
        # Prepare query parameters
        query_params = {
            'FilterExpression': "(approval_status = :status OR approval_status = :namespaced_status) AND begins_with(id, :site_prefix)",
            'ExpressionAttributeValues': {
                ":status": "APPROVED",
                ":namespaced_status": f"{site_slug}!APPROVED",
                ":site_prefix": f"{site_slug}!"
            }
        }
        
        # Get all approved groups by paginating automatically
        all_groups = []
        current_key = last_evaluated_key
        
        # Continue querying until we have all results or reach the limit
        while True:
            # Add ExclusiveStartKey for pagination if we have one
            if current_key:
                query_params['ExclusiveStartKey'] = current_key
            
            # Query the groups table
            response = groups_table.scan(**query_params)
            
            # Add the items to our result list
            all_groups.extend(response.get('Items', []))
            
            # Check if we have more results
            current_key = response.get('LastEvaluatedKey')
            
            # If no more results or we've reached the limit, break
            if not current_key or len(all_groups) >= limit:
                break
        
        # Sort groups by name
        all_groups.sort(key=lambda x: x.get('name', '').lower())
        
        # Limit the number of groups if needed
        if len(all_groups) > limit:
            all_groups = all_groups[:limit]
        
        # Prepare groups for template rendering
        prepared_groups = [prepare_group_for_template(group) for group in all_groups]
        
        # Return the groups and the last evaluated key (None since we've fetched all)
        return prepared_groups, None
    except Exception as e:
        logger.error(f"Error getting approved groups: {str(e)}")
        return [], None

def get_all_groups():
    """
    Queries the DynamoDB table for all groups.
    
    Returns:
        List of all groups
    """
    try:
        # Initialize the groups table
        groups_table = get_groups_table()
        
        # Get site slug
        site_slug = get_site_slug()
        
        # Query the groups table for all groups with the site prefix
        response = groups_table.scan(
            FilterExpression="begins_with(id, :site_prefix) OR begins_with(approval_status, :site_prefix)",
            ExpressionAttributeValues={
                ":site_prefix": f"{site_slug}!"
            }
        )
        
        # Get the groups from the response
        groups = response.get('Items', [])
        
        # Sort groups by name
        groups.sort(key=lambda x: x.get('name', '').lower())
        
        # Prepare groups for template rendering
        prepared_groups = [prepare_group_for_template(group) for group in groups]
        
        return prepared_groups
    except Exception as e:
        logger.error(f"Error getting all groups: {str(e)}")
        return []

def get_pending_groups(last_evaluated_key=None, limit=50):
    """
    Queries the DynamoDB table for pending groups.
    
    Args:
        last_evaluated_key: The LastEvaluatedKey from the previous query for pagination
        limit: Maximum number of items to return
        
    Returns:
        Tuple of (list of pending groups, LastEvaluatedKey for pagination)
    """
    try:
        # Initialize the groups table
        groups_table = get_groups_table()
        
        # Get site slug
        site_slug = get_site_slug()
        
        # Prepare query parameters
        query_params = {
            'FilterExpression': "(approval_status = :status OR approval_status = :namespaced_status) AND begins_with(id, :site_prefix)",
            'ExpressionAttributeValues': {
                ":status": "PENDING",
                ":namespaced_status": f"{site_slug}!PENDING",
                ":site_prefix": f"{site_slug}!"
            }
        }
        
        # Get all pending groups by paginating automatically
        all_groups = []
        current_key = last_evaluated_key
        
        # Continue querying until we have all results or reach the limit
        while True:
            # Add ExclusiveStartKey for pagination if we have one
            if current_key:
                query_params['ExclusiveStartKey'] = current_key
            
            # Query the groups table
            response = groups_table.scan(**query_params)
            
            # Add the items to our result list
            all_groups.extend(response.get('Items', []))
            
            # Check if we have more results
            current_key = response.get('LastEvaluatedKey')
            
            # If no more results or we've reached the limit, break
            if not current_key or len(all_groups) >= limit:
                break
        
        # Sort groups by name
        all_groups.sort(key=lambda x: x.get('name', '').lower())
        
        # Limit the number of groups if needed
        if len(all_groups) > limit:
            all_groups = all_groups[:limit]
        
        # Prepare groups for template rendering
        prepared_groups = [prepare_group_for_template(group) for group in all_groups]
        
        # Return the groups and the last evaluated key (None since we've fetched all)
        return prepared_groups, None
    except Exception as e:
        logger.error(f"Error getting pending groups: {str(e)}")
        return [], None

def get_group_by_id(group_id):
    """
    Get a group by its ID.
    
    Args:
        group_id: The ID of the group to get
        
    Returns:
        The group object or None if not found
    """
    try:
        # Initialize the groups table
        groups_table = get_groups_table()
        
        # Get the group
        response = groups_table.get_item(
            Key={
                'id': group_id
            }
        )
        
        # Return the group if found
        if 'Item' in response:
            return prepare_group_for_template(response['Item'])
        else:
            return None
    except Exception as e:
        logger.error(f"Error getting group by ID: {str(e)}")
        return None

def approve_group(group_id):
    """
    Approve a group by setting its approval_status to 'APPROVED'.
    
    Args:
        group_id: The ID of the group to approve
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Initialize the groups table
        groups_table = get_groups_table()
        
        # Get site slug
        site_slug = get_site_slug()
        
        # Update the group
        groups_table.update_item(
            Key={
                'id': group_id
            },
            UpdateExpression="SET approval_status = :status, updated_at = :updated_at",
            ExpressionAttributeValues={
                ":status": f"{site_slug}!APPROVED",
                ":updated_at": datetime.now().isoformat()
            }
        )
        
        return True, "Group approved successfully"
    except Exception as e:
        logger.error(f"Error approving group: {str(e)}")
        return False, str(e)

def delete_group(group_id):
    """
    Delete a group from the database.
    
    Args:
        group_id: The ID of the group to delete
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Initialize the groups table
        groups_table = get_groups_table()
        
        # Delete the group
        groups_table.delete_item(
            Key={
                'id': group_id
            }
        )
        
        return True, "Group deleted successfully"
    except Exception as e:
        logger.error(f"Error deleting group: {str(e)}")
        return False, str(e)

def set_group_pending(group_id):
    """
    Set a group's approval_status to 'PENDING'.
    
    Args:
        group_id: The ID of the group to set as pending
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Initialize the groups table
        groups_table = get_groups_table()
        
        # Get site slug
        site_slug = get_site_slug()
        
        # Update the group
        groups_table.update_item(
            Key={
                'id': group_id
            },
            UpdateExpression="SET approval_status = :status, updated_at = :updated_at",
            ExpressionAttributeValues={
                ":status": f"{site_slug}!PENDING",
                ":updated_at": datetime.now().isoformat()
            }
        )
        
        return True, "Group set to pending successfully"
    except Exception as e:
        logger.error(f"Error setting group to pending: {str(e)}")
        return False, str(e)

def update_group(group_id, group_data):
    """
    Update a group's information.
    
    Args:
        group_id: The ID of the group to update
        group_data: Dictionary containing the updated group data
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Initialize the groups table
        groups_table = get_groups_table()
        
        # Build update expression and attribute values
        update_expr = "SET updated_at = :updated_at"
        expr_attr_values = {
            ":updated_at": datetime.now().isoformat()
        }
        
        # Add fields to update
        for key, value in group_data.items():
            if key not in ['id', 'created_at']:  # Don't update these fields
                update_expr += f", {key} = :{key}"
                expr_attr_values[f":{key}"] = value
        
        # Update the group
        groups_table.update_item(
            Key={
                'id': group_id
            },
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_values
        )
        
        return True, "Group updated successfully"
    except Exception as e:
        logger.error(f"Error updating group: {str(e)}")
        return False, str(e)

def import_groups_from_csv(csv_data):
    """
    Import groups from CSV data.
    
    Args:
        csv_data: CSV data as a string
        
    Returns:
        Tuple of (success, message, count)
    """
    try:
        # Initialize the groups table
        groups_table = get_groups_table()
        
        # Get site slug
        site_slug = get_site_slug()
        
        # Parse CSV data
        csv_file = io.StringIO(csv_data)
        reader = csv.DictReader(csv_file)
        
        # Track groups we've already processed to avoid duplicates
        processed_names = set()
        groups_loaded = 0
        
        # Process each row in the CSV
        for row in reader:
            # Skip if we've already processed this group name
            if row['name'] in processed_names:
                logger.info(f"Skipping duplicate group: {row['name']}")
                continue
            
            # Add to processed set
            processed_names.add(row['name'])
            
            # Generate a unique ID for the group with site prefix
            group_id = f"{site_slug}!{str(uuid.uuid4())}"
            
            # Create the group item with sanitized text
            group_item = {
                'id': group_id,
                'name': sanitize_text(row['name']),
                'website': sanitize_text(row['website']),
                'ical': sanitize_text(row.get('ical', '')),
                'approval_status': f"{site_slug}!APPROVED",  # Set status to approved by default
                'active': True,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'organization_name': sanitize_text(row['name'])  # Using name as organization_name for GSI
            }
            
            # Add fallback_url if it exists
            if 'fallback_url' in row and row['fallback_url']:
                group_item['fallback_url'] = sanitize_text(row['fallback_url'])
            
            # Put the item in the DynamoDB table
            groups_table.put_item(Item=group_item)
            groups_loaded += 1
        
        return True, f"Successfully imported {groups_loaded} groups", groups_loaded
    except Exception as e:
        logger.error(f"Error importing groups from CSV: {str(e)}")
        return False, str(e), 0

def export_groups_to_csv():
    """
    Export groups to CSV format.
    
    Returns:
        CSV data as a string
    """
    try:
        # Get all groups
        groups = get_all_groups()
        
        # Create a CSV string
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['name', 'fallback_url', 'ical', 'website'])
        writer.writeheader()
        
        # Write each group to the CSV
        for group in groups:
            writer.writerow({
                'name': group.get('name', ''),
                'fallback_url': group.get('fallback_url', ''),
                'ical': group.get('ical', ''),
                'website': group.get('website', '')
            })
        
        return output.getvalue()
    except Exception as e:
        logger.error(f"Error exporting groups to CSV: {str(e)}")
        return ""

def get_events(start_date=None, additional_months=0, status=None):
    """
    Returns a list of tuples, each containing a day dictionary and a list of events.
    Includes days without events.
    
    Args:
        start_date: The date to start from (defaults to today in US/Eastern timezone)
        additional_months: Number of additional months to include (default 0)
        status: Filter events by status (e.g., 'APPROVED', 'PENDING', None for all)
    
    Returns:
        List of days with events, each day is a dictionary with date, short_date, and events
    """
    try:
        # Initialize the events table
        events_table = get_events_table()
        
        # Get site slug
        site_slug = get_site_slug()
        
        # Get current date in US/Eastern timezone if start_date is not provided
        if start_date is None:
            current_date = datetime.now(eastern).date()
        elif isinstance(start_date, str):
            current_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            current_date = start_date
        
        current_day = current_date.day
        current_month = current_date.month
        current_year = current_date.year
        
        logger.info(f"Getting events from {current_date} for {additional_months+1} months")
        
        # Get the month keys for the specified period
        months_to_query = []
        # Start with current month
        current_month_key = f"{site_slug}#EventsForMonth{current_year}-{current_month:02d}"
        months_to_query.append(current_month_key)
        
        # Add additional months if needed
        for i in range(1, additional_months + 1):
            # Calculate the next month
            next_month_date = datetime(current_year, current_month, 1) + timedelta(days=32 * i)
            next_month_date = next_month_date.replace(day=1)  # First day of the next month
            next_month_key = f"{site_slug}#EventsForMonth{next_month_date.year}-{next_month_date.month:02d}"
            if next_month_key not in months_to_query:
                months_to_query.append(next_month_key)
        
        # Log the months we're querying
        logger.info(f"Querying months: {pretty_json(months_to_query)}")
        
        all_events = []
        
        # Query each month
        for month_key in months_to_query:
            query_params = {
                'KeyConditionExpression': Key('month').eq(month_key)
            }
            
            # Add status filter if provided
            if status:
                query_params['FilterExpression'] = Attr('status').eq(status)
            
            logger.info(f"Querying month {month_key}")
            response = events_table.query(**query_params)
            month_events = response.get('Items', [])
            logger.info(f"Found {len(month_events)} events for month {month_key}")
            
            # Filter events by date if it's the current month
            if month_key == current_month_key:
                filtered_events = []
                for event in month_events:
                    # Extract date from startDate field
                    if 'localstartDate' in event:
                        event_date = datetime.fromisoformat(event['localstartDate'].replace('Z', '+00:00'))
                    elif 'startDate' in event:
                        event_date = datetime.fromisoformat(event['startDate'].replace('Z', '+00:00'))
                    else:
                        continue
                    
                    # Convert to Eastern time for comparison
                    eastern_date = event_date.astimezone(eastern)
                    event_day = eastern_date.day
                    
                    # Only include events from current day onwards
                    if event_day >= current_day:
                        filtered_events.append(event)
                
                all_events.extend(filtered_events)
            else:
                all_events.extend(month_events)
        
        logger.info(f"Total events found: {len(all_events)}")
        
        # Create a dictionary to store events by day
        events_by_day = {}
        
        # Calculate the end date based on additional_months
        if additional_months == 0:
            # If no additional months, show the rest of the current month
            last_day_of_month = datetime(current_year, current_month, 1)
            # Move to the next month and then back one day to get the last day of the current month
            if current_month == 12:
                last_day_of_month = datetime(current_year + 1, 1, 1) - timedelta(days=1)
            else:
                last_day_of_month = datetime(current_year, current_month + 1, 1) - timedelta(days=1)
            end_date = last_day_of_month.date()
        else:
            # Calculate the last day of the last month to include
            last_month_date = datetime(current_year, current_month, 1) + timedelta(days=32 * additional_months)
            last_month_date = last_month_date.replace(day=1) - timedelta(days=1)
            end_date = last_month_date.date()
        
        # Generate all days in the range, including those without events
        total_days = (end_date - current_date).days + 1
        start_day = current_date
        
        # Create entries for all days in the range
        for i in range(total_days):
            day_date = start_day + timedelta(days=i)
            day_key = day_date.strftime('%Y-%m-%d')
            short_date = day_date.strftime('%a %-m/%-d')  # Format as "Mon 5/5"
            
            events_by_day[day_key] = {
                'date': day_key,
                'short_date': short_date,
                'events': []
            }
        
        # Add events to their respective days
        for event in all_events:
            try:
                # Extract date from startDate field
                if 'localstartDate' in event:
                    event_date = datetime.fromisoformat(event['localstartDate'].replace('Z', '+00:00'))
                elif 'startDate' in event:
                    event_date = datetime.fromisoformat(event['startDate'].replace('Z', '+00:00'))
                else:
                    logger.warning(f"Event missing date information: {event.get('id', 'unknown')}")
                    continue
                
                # Convert to Eastern time for display
                eastern_date = event_date.astimezone(eastern)
                day_key = eastern_date.strftime('%Y-%m-%d')
                
                # Skip if this day is not in our range
                if day_key not in events_by_day:
                    continue
                
                # Format the event for display
                formatted_event = {
                    'id': event.get('id', ''),
                    'title': sanitize_text(event.get('title', '')),
                    'date': day_key,
                    'time': eastern_date.strftime('%-I:%M %p').lower(),  # Format as "1:30 pm"
                    'url': sanitize_text(event.get('url', '')),
                    'description': sanitize_text(event.get('description', '')),
                    'group': sanitize_text(event.get('groupName', event.get('group', ''))),
                    'status': event.get('status', '')
                }
                
                # Apply full template preparation
                formatted_event = prepare_event_for_template(formatted_event)
                
                # Add location if available
                if 'location' in event:
                    formatted_event['location'] = sanitize_text(event['location'])
                
                events_by_day[day_key]['events'].append(formatted_event)
            except Exception as e:
                logger.error(f"Error processing event: {str(e)}, Event: {pretty_json(event)}")
                continue
        
        # Convert the dictionary to a sorted list of days
        sorted_days = sorted(events_by_day.keys())
        days_data = [events_by_day[day] for day in sorted_days]
        
        # Sort events within each day by time
        for day_data in days_data:
            day_data['events'] = sorted(day_data['events'], key=lambda x: x.get('time', ''))
            # Add a flag to indicate if the day has events
            day_data['has_events'] = len(day_data['events']) > 0
        
        logger.info(f"Final structure: {len(days_data)} days with events")
        return days_data
    except Exception as e:
        logger.error(f"Error getting events: {str(e)}")
        return []