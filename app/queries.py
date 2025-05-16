import json
import os
import boto3
import logging
from datetime import datetime, timedelta
import pathlib
import time
import pytz
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
dynamodb = boto3.resource('dynamodb',endpoint_url='http://dynamodb-local:8000')
# Initialize timezone
eastern = pytz.timezone('US/Eastern')

# Set up pretty printing for JSON logs
def pretty_json(obj):
    return json.dumps(obj, indent=2, default=str)


def get_approved_groups():
    """
    Queries the DynamoDB table for approved groups.
    
    Returns:
        List of approved groups
    """
    try:
        # Get the groups table name from environment variable
        groups_table_name = os.environ.get('GROUPS_TABLE', 'ApiStack-GroupsTableE5F9C3F0-1DCYN83WUFZWG')
        if not groups_table_name:
            logger.warning("GROUPS_TABLE environment variable is not set")
            return []
        
        # Initialize the groups table
        groups_table = dynamodb.Table(groups_table_name)
        
        # Get SITEURL from environment or use default
        site_url = os.environ.get('SITEURL', 'http://localhost:5000')
        # Remove trailing slash if present
        if site_url.endswith('/'):
            site_url = site_url[:-1]
        # Create a site slug for filtering by ID prefix
        site_slug = site_url.replace('http://', '').replace('https://', '').replace(':', '_').replace('/', '_')
        
        # Query the groups table for approved groups with the site prefix
        response = groups_table.scan(
            FilterExpression="approval_status = :status AND begins_with(id, :site_prefix)",
            ExpressionAttributeValues={
                ":status": "approved",
                ":site_prefix": f"{site_slug}#"
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
        logger.error(f"Error getting approved groups: {str(e)}")
        return []

def get_events(start_date=None, additional_weeks=3, status=None):
    """
    Queries the DynamoDB table for events starting from a specific date and for a number of weeks.
    Returns a list of tuples, each containing a day dictionary and a list of events.
    Includes days without events.
    
    Args:
        start_date: The date to start from (defaults to today in US/Eastern timezone)
        additional_weeks: Number of additional weeks to include (default 3)
        status: Filter events by status (e.g., 'APPROVED', 'PENDING', None for all)
    
    Returns:
        List of days with events, each day is a dictionary with date, short_date, and events
    """
    try:
        # Get the events table name from environment variable
        events_table_name = os.environ.get('EVENTS_TABLE', 'ApiStack-EventsTableD24865E5-1L3ICZOHO627W')
        if not events_table_name:
            logger.warning("EVENTS_TABLE environment variable is not set")
            return []
        
        # Initialize the events table
        events_table = dynamodb.Table(events_table_name)
        
        # Get SITEURL from environment or use default
        site_url = os.environ.get('SITEURL', 'http://localhost:5000')
        # Remove trailing slash if present
        if site_url.endswith('/'):
            site_url = site_url[:-1]
        # Create a site slug for the partition key prefix
        site_slug = site_url.replace('http://', '').replace('https://', '').replace(':', '_').replace('/', '_')
        
        # Get current date in US/Eastern timezone if start_date is not provided
        if start_date is None:
            current_date = datetime.now(eastern).date()
        elif isinstance(start_date, str):
            current_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            current_date = start_date
        
        current_weekday = current_date.isoweekday()  # 1=Monday through 7=Sunday
        
        logger.info(f"Getting events from {current_date} (weekday {current_weekday}) for {additional_weeks+1} weeks")
        
        # Get the ISO week keys for the specified weeks
        weeks_to_query = []
        for i in range(additional_weeks + 1):  # Start week + additional weeks
            future_date = current_date + timedelta(weeks=i)
            week_key = f"{site_slug}#EventsForWeek{future_date.strftime('%G-W%V')}"
            weeks_to_query.append((week_key, i))
        
        # Log the weeks we're querying
        logger.info(f"Querying weeks: {pretty_json([w[0] for w in weeks_to_query])}")
        
        all_events = []
        
        # Query each week with appropriate day filter
        for week_key, week_index in weeks_to_query:
            # For the first week, we only want events from the current weekday onwards
            if week_index == 0:
                # For first week, filter by weekday using sort key
                for day in range(current_weekday, 8):  # From current day to Sunday
                    query_params = {
                        'KeyConditionExpression': Key('week').eq(week_key) & 
                                                  Key('sort').begins_with(f"{day}-")
                    }
                    
                    # Add status filter if provided
                    if status:
                        query_params['FilterExpression'] = Attr('status').eq(status)
                    
                    logger.info(f"Querying week {week_key} for day {day}")
                    response = events_table.query(**query_params)
                    week_events = response.get('Items', [])
                    logger.info(f"Found {len(week_events)} events for week {week_key}, day {day}")
                    all_events.extend(week_events)
            else:
                # For future weeks, get all days
                query_params = {
                    'KeyConditionExpression': Key('week').eq(week_key)
                }
                
                # Add status filter if provided
                if status:
                    query_params['FilterExpression'] = Attr('status').eq(status)
                
                logger.info(f"Querying week {week_key} for all days")
                response = events_table.query(**query_params)
                week_events = response.get('Items', [])
                logger.info(f"Found {len(week_events)} events for week {week_key}")
                all_events.extend(week_events)
        
        logger.info(f"Total events found: {len(all_events)}")
        
        # Create a dictionary to store events by day
        events_by_day = {}
        
        # Generate all days in the range, including those without events
        total_days = (additional_weeks + 1) * 7
        if week_index == 0:
            # For the first week, start from the current day
            start_day = current_date
        else:
            # For subsequent weeks, start from Monday
            monday_offset = (current_date.weekday()) % 7
            start_day = current_date - timedelta(days=monday_offset)
        
        # Create entries for all days in the range
        for i in range(total_days):
            day_date = start_day + timedelta(days=i)
            
            # Skip days before the current date
            if day_date < current_date:
                continue
                
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