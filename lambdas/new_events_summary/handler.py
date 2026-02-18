import os
import json
import boto3
import requests
import yaml
from datetime import datetime
import pytz
import sys

# Add current directory to path
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

def get_microblog_token(secret_name):
    """Fetch Micro.blog token from AWS Secrets Manager."""
    client = boto3.client('secretsmanager')
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return response.get('SecretString')
    except Exception as e:
        print(f"Error fetching secret {secret_name}: {e}")
        return None

def get_todays_new_events(target_date):
    """Get events added on target date."""
    recent_events = db_utils.get_recently_added(limit=100)
    # Filter out hidden and duplicate events
    recent_events = [e for e in recent_events if not e.get('hidden') and not e.get('duplicate_of')]
    
    new_events = []
    
    for event in recent_events:
        created_at = event.get('createdAt')
        if not created_at:
            continue
        
        try:
            # Parse UTC timestamp
            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            # Convert to local and check date
            if dt.astimezone(local_tz).date() == target_date:
                new_events.append(event)
        except (ValueError, AttributeError):
            continue
    
    return new_events

def generate_summary_content(count, target_date):
    """Generate summary content with link to just-added page."""
    anchor = f"{target_date.month}-{target_date.day}-{target_date.year}"
    url = f"{BASE_URL}/just-added/#{anchor}"
    event_word = 'event' if count == 1 else 'events'
    return f"{count} new {event_word} added today: {url}"

def post_to_microblog(content, token):
    """Post to micro.blog."""
    headers = {'Authorization': f'Bearer {token}'}
    data = {'h': 'entry', 'content': content}
    
    # Always try to resolve the UID for the destination
    target_destination = get_micropub_destination(token)
    data['mp-destination'] = target_destination

    try:
        response = requests.post(MICROPUB_ENDPOINT, data=data, headers=headers, timeout=30)
        if response.status_code >= 500:
            return True
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error posting: {e}")
        return False

def lambda_handler(event, context):
    """AWS Lambda entry point for new events summary (9:30 PM)."""
    print("Starting new events summary...")
    
    secret_name = os.environ.get('MB_TOKEN_SECRET_NAME', 'dctech-events/microblog-token')
    token = get_microblog_token(secret_name)
    if not token:
        return {'statusCode': 500, 'body': 'Error: Token not found'}

    target_date = datetime.now(local_tz).date()
    new_events = get_todays_new_events(target_date)
    
    if not new_events:
        print(f"No new events for {target_date}. Skipping.")
        return {'statusCode': 200, 'body': 'No new events to post'}

    content = generate_summary_content(len(new_events), target_date)
    print(f"Posting: {content}")
    success = post_to_microblog(content, token)
    
    return {'statusCode': 200 if success else 500, 'body': 'Success' if success else 'Failed'}
