import os
import json
import boto3
import requests
import yaml
from datetime import datetime, timedelta
import pytz
import sys

# Add current directory to path
sys.path.append(os.path.dirname(__file__))
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
SITE_NAME = config.get('site_name', 'DC Tech Events')
BASE_URL = config.get('base_url', 'https://dctech.events')

# Micropub endpoint
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

def get_week_identifier(target_date):
    """Get the ISO week identifier (YYYY-Www) for a given date."""
    iso_year, iso_week, _ = target_date.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"

def get_week_url(target_date):
    """Get the full URL for the weekly events page."""
    week_id = get_week_identifier(target_date)
    return f"{BASE_URL}/week/{week_id}/"

def format_short_date(target_date):
    """Format a date as M/D/YY (no leading zeros)."""
    return f"{target_date.month}/{target_date.day}/{target_date.strftime('%y')}"

def generate_note_content(target_date):
    """Generate the note content for the weekly post."""
    short_date = format_short_date(target_date)
    week_url = get_week_url(target_date)
    return f"{SITE_NAME} for the week of {short_date}: {week_url}"

def post_to_microblog(content, token, destination=None):
    """Post a note to micro.blog using form-encoded Micropub."""
    headers = {
        'Authorization': f'Bearer {token}',
    }

    # Form-encoded payload — no 'name' so it posts as a note
    data = {
        'h': 'entry',
        'content': content,
    }

    # Always try to resolve the UID for the destination
    target_destination = get_micropub_destination(token, destination or 'https://updates.dctech.events/')
    data['mp-destination'] = target_destination

    try:
        response = requests.post(
            MICROPUB_ENDPOINT,
            data=data,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        post_url = response.headers.get('Location', 'posted successfully')
        print(f"Successfully posted to micro.blog: {post_url}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error posting to micro.blog: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        return False

def lambda_handler(event, context):
    """AWS Lambda entry point."""
    print("Starting weekly newsletter post to Micro.blog...")
    
    secret_name = os.environ.get('MB_TOKEN_SECRET_NAME', 'dctech-events/microblog-token')
    token = get_microblog_token(secret_name)
    
    if not token:
        return {
            'statusCode': 500,
            'body': json.dumps('Error: Micro.blog token not found in Secrets Manager')
        }

    # Get current date in configured timezone (should be a Monday)
    now = datetime.now(local_tz)
    current_date = now.date()

    # Calculate the Monday of this week (even if triggered on a different day)
    days_since_monday = current_date.weekday()  # 0 = Monday, 6 = Sunday
    monday_date = current_date - timedelta(days=days_since_monday)

    print(f"Posting newsletter note for the week of {monday_date.strftime('%A, %B %-d, %Y')}...")

    # Generate note content
    content = generate_note_content(monday_date)
    print(f"Content: {content}")

    # Post to micro.blog
    success = post_to_microblog(
        content=content,
        token=token,
        destination='https://updates.dctech.events/'
    )

    if success:
        return {
            'statusCode': 200,
            'body': json.dumps('Successfully posted newsletter to Micro.blog')
        }
    else:
        return {
            'statusCode': 500,
            'body': json.dumps('Failed to post newsletter to Micro.blog')
        }
