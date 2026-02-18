import os
import json
import boto3
import requests
import yaml
from datetime import datetime
import pytz
import sys

# Add current directory to path so we can import db_utils and common
sys.path.append(os.path.dirname(__file__))
import db_utils
from common.microblog import get_micropub_destination

# Load configuration
CONFIG_FILE = 'config.yaml'
config = {}
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r') as f:
        config = yaml.safe_load(f)

# Define timezone from config
timezone_name = config.get('timezone', 'US/Eastern')
local_tz = pytz.timezone(timezone_name)

# Get site configuration
BASE_URL = config.get('base_url', 'https://dctech.events')

# Micro.blog API configuration
MICROPUB_ENDPOINT = "https://micro.blog/micropub"
CHAR_LIMIT = 300

def get_microblog_token(secret_name):
    """Fetch Micro.blog token from AWS Secrets Manager."""
    client = boto3.client('secretsmanager')
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return response.get('SecretString')
    except Exception as e:
        print(f"Error fetching secret {secret_name}: {e}")
        return None

def is_virtual_event(event):
    """Determine if an event is virtual."""
    return event.get('location_type') == 'virtual'

def get_events_for_date(events, target_date):
    """Filter events for a specific date."""
    target_date_str = target_date.strftime('%Y-%m-%d')
    matching_events = []
    
    for event in events:
        event_date = event.get('date')
        if not event_date:
            continue
        
        if event_date == target_date_str:
            matching_events.append(event)
            continue
        
        end_date_str = event.get('end_date')
        if end_date_str:
            try:
                event_start = datetime.strptime(event_date, '%Y-%m-%d').date()
                event_end = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                if event_start <= target_date <= event_end:
                    matching_events.append(event)
            except (ValueError, TypeError):
                pass
    
    return matching_events

def get_week_url(target_date):
    """Generate the week URL with date anchor."""
    week = target_date.isocalendar()
    return f"{BASE_URL}/week/{week.year}-W{week.week:02d}/#{target_date.strftime('%Y-%m-%d')}"

def create_post_text(events, target_date):
    """Create post text for micro.blog under 300 characters."""
    url = get_week_url(target_date)
    prefix = "DC Tech Events today: "
    suffix = f"  {url}"
    
    overhead = len(prefix) + len(suffix)
    event_titles = [event.get('title', 'Untitled Event') for event in events]
    
    if not event_titles:
        return None
    
    if len(event_titles) == 1:
        text = f"{prefix}{event_titles[0]}{suffix}"
        if len(text) <= CHAR_LIMIT:
            return text
        max_title_len = CHAR_LIMIT - overhead - 3
        truncated_title = event_titles[0][:max_title_len] + "..."
        return f"{prefix}{truncated_title}{suffix}"
    
    for num_to_show in range(len(event_titles), 0, -1):
        if num_to_show == len(event_titles):
            event_list = ", ".join(event_titles)
            text = f"{prefix}{event_list}{suffix}"
            if len(text) <= CHAR_LIMIT:
                return text
        else:
            shown_events = event_titles[:num_to_show]
            remaining = len(event_titles) - num_to_show
            event_list = ", ".join(shown_events) + f", and {remaining} more"
            text = f"{prefix}{event_list}{suffix}"
            if len(text) <= CHAR_LIMIT:
                return text
    
    return f"{prefix}{len(event_titles)} events{suffix}"

def post_to_microblog(content, token):
    """Post a note to micro.blog."""
    headers = {'Authorization': f'Bearer {token}'}
    data = {'h': 'entry', 'content': content}
    
    # Always try to resolve the UID for the destination
    target_destination = get_micropub_destination(token)
    data['mp-destination'] = target_destination

    try:
        response = requests.post(MICROPUB_ENDPOINT, data=data, headers=headers, timeout=30)
        # Non-fatal server errors
        if response.status_code >= 500:
            print(f"Warning: micro.blog server error ({response.status_code})")
            return True
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error posting to micro.blog: {e}")
        return False

def lambda_handler(event, context):
    """AWS Lambda entry point for daily summary (8 AM)."""
    print("Starting daily event summary...")
    
    secret_name = os.environ.get('MB_TOKEN_SECRET_NAME', 'dctech-events/microblog-token')
    token = get_microblog_token(secret_name)
    if not token:
        return {'statusCode': 500, 'body': 'Error: Micro.blog token not found'}

    target_date = datetime.now(local_tz).date()
    print(f"Checking events for {target_date}...")
    
    all_events = db_utils.get_future_events()
    # Filter out hidden and duplicate events
    all_events = [e for e in all_events if not e.get('hidden') and not e.get('duplicate_of')]
    
    events = get_events_for_date(all_events, target_date)
    in_person_events = [e for e in events if not is_virtual_event(e)]
    
    if not in_person_events:
        print(f"No in-person events for {target_date}. Skipping.")
        return {'statusCode': 200, 'body': 'No events to post'}

    post_text = create_post_text(in_person_events, target_date)
    if not post_text:
        return {'statusCode': 200, 'body': 'Could not generate post text'}

    print(f"Posting: {post_text}")
    success = post_to_microblog(post_text, token)
    
    return {'statusCode': 200 if success else 500, 'body': 'Success' if success else 'Failed'}
