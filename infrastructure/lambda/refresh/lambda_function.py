"""
Lambda function to sync groups/events from GitHub repo and fetch iCal feeds.

This function runs every 4 hours and performs three tasks:
1. Sync groups from _groups/*.yaml in GitHub repo
2. Sync single events from _single_events/*.yaml in GitHub repo
3. Fetch iCal feeds for all active groups

This keeps next.dctech.events in sync with the GitHub repo.
"""

import json
import yaml
import os
import time
import boto3
import hashlib
from datetime import datetime, timedelta
from github import Github
from icalendar import Calendar
import requests

# AWS clients
dynamodb = boto3.resource('dynamodb')
secretsmanager = boto3.client('secretsmanager')

# DynamoDB tables
groups_table = dynamodb.Table(os.environ['GROUPS_TABLE'])
events_table = dynamodb.Table(os.environ['EVENTS_TABLE'])


def get_github_token():
    """Retrieve GitHub token from Secrets Manager"""
    try:
        secret_name = os.environ.get('GITHUB_TOKEN_SECRET', 'dctech-events/github-token')
        response = secretsmanager.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except Exception as e:
        print(f"Error retrieving GitHub token: {str(e)}")
        return None


def sync_groups_from_repo(github_client):
    """Sync group definitions from _groups/ directory in repo"""
    groups_synced = 0

    try:
        repo_name = os.environ.get('GITHUB_REPO', 'rosskarchner/dctech.events')
        repo = github_client.get_repo(repo_name)

        # Fetch all files in _groups/ directory
        contents = repo.get_contents('_groups')

        for item in contents:
            if not item.name.endswith('.yaml'):
                continue

            try:
                # Parse YAML content
                yaml_content = item.decoded_content.decode('utf-8')
                group_data = yaml.safe_load(yaml_content)

                # Use filename (without .yaml) as groupId for consistency
                group_id = item.name.replace('.yaml', '')

                # Create group record
                timestamp = datetime.utcnow().isoformat() + 'Z'
                group = {
                    'groupId': group_id,
                    'name': group_data.get('name', ''),
                    'website': group_data.get('website', ''),
                    'ical': group_data.get('ical', ''),
                    'active': 'true' if group_data.get('active', True) else 'false',
                    'description': group_data.get('description', ''),
                    'fallback_url': group_data.get('fallback_url', ''),
                    'createdAt': timestamp,
                    'createdBy': 'repo_sync',
                    'sourceFile': item.name,
                    'lastSyncedAt': timestamp,
                }

                groups_table.put_item(Item=group)
                groups_synced += 1
                print(f"Synced group: {group_data.get('name')}")

            except Exception as e:
                print(f"Error syncing group {item.name}: {str(e)}")

    except Exception as e:
        print(f"Error fetching groups from repo: {str(e)}")

    return groups_synced


def sync_single_events_from_repo(github_client):
    """Sync manually submitted events from _single_events/ directory"""
    events_synced = 0

    try:
        repo_name = os.environ.get('GITHUB_REPO', 'rosskarchner/dctech.events')
        repo = github_client.get_repo(repo_name)

        # Fetch all files in _single_events/ directory
        try:
            contents = repo.get_contents('_single_events')
        except Exception as e:
            print(f"Error fetching _single_events directory: {str(e)}. Skipping single events sync.")
            return 0

        for item in contents:
            if not item.name.endswith('.yaml'):
                continue

            try:
                # Parse YAML content
                yaml_content = item.decoded_content.decode('utf-8')
                event_data = yaml.safe_load(yaml_content)

                # Use filename as eventId for consistency
                event_id = item.name.replace('.yaml', '')

                # Create event record
                timestamp = datetime.utcnow().isoformat() + 'Z'
                event = {
                    'eventId': event_id,
                    'title': event_data.get('title', ''),
                    'description': event_data.get('description', ''),
                    'location': event_data.get('location', ''),
                    'eventDate': event_data.get('date', ''),
                    'time': event_data.get('time', '00:00'),
                    'url': event_data.get('url', ''),
                    'eventType': 'all',
                    'createdAt': timestamp,
                    'createdBy': 'repo_sync',
                    'sourceFile': item.name,
                    'lastSyncedAt': timestamp,
                }

                # Add optional fields
                if event_data.get('end_date'):
                    event['endDate'] = event_data.get('end_date')
                if event_data.get('end_time'):
                    event['endTime'] = event_data.get('end_time')
                if event_data.get('cost'):
                    event['cost'] = event_data.get('cost')

                events_table.put_item(Item=event)
                events_synced += 1
                print(f"Synced event: {event_data.get('title')}")

            except Exception as e:
                print(f"Error syncing event {item.name}: {str(e)}")

    except Exception as e:
        print(f"Error fetching events from repo: {str(e)}")

    return events_synced


def fetch_ical_feed(url):
    """Fetch and parse an iCal feed"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        cal = Calendar.from_ical(response.content)
        events = []

        for component in cal.walk():
            if component.name == "VEVENT":
                event = {}

                # Extract event data
                if 'SUMMARY' in component:
                    event['title'] = str(component.get('SUMMARY'))

                if 'DTSTART' in component:
                    dtstart = component.get('DTSTART').dt
                    if isinstance(dtstart, datetime):
                        event['eventDate'] = dtstart.strftime('%Y-%m-%d')
                        event['time'] = dtstart.strftime('%H:%M')
                    else:
                        event['eventDate'] = str(dtstart)
                        event['time'] = '00:00'

                if 'DESCRIPTION' in component:
                    event['description'] = str(component.get('DESCRIPTION'))

                if 'LOCATION' in component:
                    event['location'] = str(component.get('LOCATION'))

                if 'URL' in component:
                    event['url'] = str(component.get('URL'))

                # Only add future events
                if 'eventDate' in event:
                    event_date = datetime.strptime(event['eventDate'], '%Y-%m-%d')
                    if event_date >= datetime.now() - timedelta(days=1):
                        events.append(event)

        return events

    except Exception as e:
        print(f"Error fetching iCal feed from {url}: {str(e)}")
        return []


def sync_ical_feeds():
    """Fetch iCal feeds for all active groups"""
    ical_events_synced = 0

    try:
        # Get all active groups
        response = groups_table.query(
            IndexName='activeGroupsIndex',
            KeyConditionExpression='active = :active',
            ExpressionAttributeValues={':active': 'true'}
        )

        groups = response.get('Items', [])
        print(f"Found {len(groups)} active groups")

        for group in groups:
            if not group.get('ical'):
                continue

            try:
                print(f"Fetching iCal for {group.get('name')}...")
                events = fetch_ical_feed(group['ical'])

                # Store events in DynamoDB
                for event in events:
                    # Generate unique event ID based on group and event data
                    # Using 32 characters (128 bits) for adequate collision resistance
                    event_hash = f"{group['groupId']}-{event.get('title', '')}-{event.get('eventDate', '')}"
                    event_id = hashlib.sha256(event_hash.encode()).hexdigest()[:32]

                    timestamp = datetime.utcnow().isoformat() + 'Z'
                    event_item = {
                        'eventId': event_id,
                        'groupId': group['groupId'],
                        'eventType': 'all',
                        'createdAt': timestamp,
                        'createdBy': 'ical_sync',
                        'lastSyncedAt': timestamp,
                        **event
                    }

                    events_table.put_item(Item=event_item)

                ical_events_synced += len(events)
                print(f"Synced {len(events)} events for {group.get('name')}")

            except Exception as e:
                print(f"Error syncing iCal for {group.get('name')}: {str(e)}")

    except Exception as e:
        print(f"Error fetching groups: {str(e)}")

    return ical_events_synced


def lambda_handler(event, context):
    """
    Main Lambda handler.
    Syncs groups and events from GitHub repo and iCal feeds.
    """
    print("Starting sync from GitHub repo and iCal feeds...")

    results = {
        'groups_synced': 0,
        'single_events_synced': 0,
        'ical_events_synced': 0,
        'status': 'success',
        'errors': []
    }

    try:
        # Get GitHub token
        github_token = get_github_token()
        if not github_token:
            raise Exception("Failed to retrieve GitHub token")

        # Initialize GitHub client
        github_client = Github(github_token)

        # Sync groups from repo
        print("Syncing groups from GitHub repo...")
        results['groups_synced'] = sync_groups_from_repo(github_client)
        print(f"Synced {results['groups_synced']} groups from repo")

        # Sync single events from repo
        print("Syncing single events from GitHub repo...")
        results['single_events_synced'] = sync_single_events_from_repo(github_client)
        print(f"Synced {results['single_events_synced']} single events from repo")

        # Sync iCal feeds
        print("Syncing iCal feeds...")
        results['ical_events_synced'] = sync_ical_feeds()
        print(f"Synced {results['ical_events_synced']} iCal events")

    except Exception as e:
        error_msg = f"Error in lambda_handler: {str(e)}"
        print(error_msg)
        results['status'] = 'error'
        results['errors'].append(error_msg)

    print(f"Sync complete: {json.dumps(results)}")

    return {
        'statusCode': 200 if results['status'] == 'success' else 500,
        'body': json.dumps(results)
    }
