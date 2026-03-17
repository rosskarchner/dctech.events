#!/usr/bin/env python3
import os
import json
import requests
import yaml
from datetime import datetime, timedelta
import pytz
import sys

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

def post_to_microblog(content, token):
    """Post a note to micro.blog."""
    if not token:
        print("Error: Micro.blog token not provided")
        return False
        
    headers = {'Authorization': f'Bearer {token}'}
    data = {'h': 'entry', 'content': content}
    
    mp_dest = os.environ.get('MP_DESTINATION')
    if mp_dest:
        data['mp-destination'] = mp_dest

    try:
        response = requests.post(MICROPUB_ENDPOINT, data=data, headers=headers, timeout=30)
        response.raise_for_status()
        print("Successfully posted to Micro.blog")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error posting to micro.blog: {e}")
        return False

def main():
    print("Starting weekly newsletter post to Micro.blog...")
    
    token = os.environ.get('MICROBLOG_TOKEN')
    if not token:
        print("Error: MICROBLOG_TOKEN environment variable not found")
        sys.exit(1)

    now = datetime.now(local_tz)
    current_date = now.date()
    days_since_monday = current_date.weekday()
    monday_date = current_date - timedelta(days=days_since_monday)

    short_date = f"{monday_date.month}/{monday_date.day}/{monday_date.strftime('%y')}"
    iso_year, iso_week, _ = monday_date.isocalendar()
    week_id = f"{iso_year}-W{iso_week:02d}"
    week_url = f"{BASE_URL}/week/{week_id}/"
    
    content = f"{SITE_NAME} for the week of {short_date}: {week_url}"
    print(f"Posting: {content}")
    post_to_microblog(content, token)

if __name__ == "__main__":
    main()
