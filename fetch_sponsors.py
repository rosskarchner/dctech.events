#!/usr/bin/env python3
"""
Fetch GitHub Sponsors.

This script queries the GitHub GraphQL API to verify sponsors and fetch their
avatar URLs. It reads the sponsors list from sponsors.yaml and
outputs to _data/sponsors.json.

The sponsor data is cached for 4 hours to avoid rate limiting.
"""

import os
import yaml
import json
import requests
from datetime import datetime, timedelta, timezone

# Constants
SPONSORS_FILE = 'sponsors.yaml'
OUTPUT_FILE = os.path.join('_data', 'sponsors.json')
CACHE_DIR = '_cache'
CACHE_FILE = os.path.join(CACHE_DIR, 'sponsors.json')
CACHE_META_FILE = os.path.join(CACHE_DIR, 'sponsors.meta')

# GitHub GraphQL API endpoint
GITHUB_API_URL = 'https://api.github.com/graphql'

# Ensure directories exist
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)


def should_fetch_sponsors():
    """
    Check if we should fetch new sponsor data based on last fetch time.

    Returns:
        bool: True if we should fetch, False if we can use cached data
    """
    if not os.path.exists(CACHE_META_FILE):
        return True

    try:
        with open(CACHE_META_FILE, 'r') as f:
            meta_data = json.load(f)

        last_fetch = meta_data.get('last_fetch')
        if last_fetch:
            last_fetch_time = datetime.fromisoformat(last_fetch)
            time_since_fetch = datetime.now(timezone.utc) - last_fetch_time
            if time_since_fetch < timedelta(hours=4):
                print(f"Sponsor data was fetched less than 4 hours ago, using cached version")
                return False
    except Exception as e:
        print(f"Error reading cache metadata: {e}")

    return True


def load_sponsors_list():
    """
    Load the list of sponsor GitHub usernames from sponsors.yaml.

    Returns:
        list: List of GitHub usernames
    """
    if not os.path.exists(SPONSORS_FILE):
        print(f"Sponsors file not found: {SPONSORS_FILE}")
        return []

    try:
        with open(SPONSORS_FILE, 'r') as f:
            data = yaml.safe_load(f)
            return data.get('sponsors', [])
    except Exception as e:
        print(f"Error loading sponsors file: {e}")
        return []


def fetch_sponsor_data(username, token):
    """
    Fetch sponsor data from GitHub GraphQL API.

    Args:
        username: GitHub username
        token: GitHub personal access token

    Returns:
        dict: Sponsor data with username, name, and avatar URL, or None if error
    """
    query = """
    query($login: String!) {
      user(login: $login) {
        login
        name
        avatarUrl
      }
    }
    """

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(
            GITHUB_API_URL,
            json={'query': query, 'variables': {'login': username}},
            headers=headers
        )
        response.raise_for_status()

        data = response.json()
        if 'errors' in data:
            print(f"GraphQL error for {username}: {data['errors']}")
            return None

        user = data.get('data', {}).get('user')
        if not user:
            print(f"User not found: {username}")
            return None

        return {
            'username': user['login'],
            'name': user.get('name', user['login']),
            'avatar_url': user['avatarUrl']
        }

    except Exception as e:
        print(f"Error fetching data for {username}: {e}")
        return None


def fetch_all_sponsors(sponsors_list, token):
    """
    Fetch data for all sponsors.

    Args:
        sponsors_list: List of GitHub usernames
        token: GitHub personal access token

    Returns:
        list: List of sponsor data dictionaries
    """
    sponsors_data = []

    for username in sponsors_list:
        if not username or not username.strip():
            continue

        print(f"Fetching data for sponsor: {username}")
        sponsor_data = fetch_sponsor_data(username.strip(), token)

        if sponsor_data:
            sponsors_data.append(sponsor_data)

    return sponsors_data


def main():
    """
    Main function to fetch and cache sponsor data.
    """
    # Check if we should use cached data
    if not should_fetch_sponsors():
        if os.path.exists(CACHE_FILE):
            print("Using cached sponsor data")
            with open(CACHE_FILE, 'r') as f:
                sponsors_data = json.load(f)

            # Copy to output location
            with open(OUTPUT_FILE, 'w') as f:
                json.dump(sponsors_data, f, indent=2)

            return 0

    # Get GitHub token from environment
    token = os.environ.get('GITHUB_SPONSORS_TOKEN')
    if not token:
        print("Warning: GITHUB_SPONSORS_TOKEN not set. Skipping sponsor fetch.")
        print("Creating empty sponsors file.")

        empty_data = []
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(empty_data, f, indent=2)

        return 0

    # Load sponsors list
    sponsors_list = load_sponsors_list()
    if not sponsors_list:
        print("No sponsors configured")

        empty_data = []
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(empty_data, f, indent=2)

        return 0

    # Fetch sponsor data
    print(f"Fetching data for {len(sponsors_list)} sponsors...")
    sponsors_data = fetch_all_sponsors(sponsors_list, token)

    # Save to cache
    with open(CACHE_FILE, 'w') as f:
        json.dump(sponsors_data, f, indent=2)

    # Save cache metadata
    meta_data = {
        'last_fetch': datetime.now(timezone.utc).isoformat()
    }
    with open(CACHE_META_FILE, 'w') as f:
        json.dump(meta_data, f)

    # Save to output location
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(sponsors_data, f, indent=2)

    print(f"Successfully fetched {len(sponsors_data)} sponsors")
    return 0


if __name__ == '__main__':
    exit(main())
