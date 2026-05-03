"""
Commit approved events and groups as YAML files to the GitHub repo.

Uses the GitHub Contents API (REST) with a PAT stored in AWS Secrets Manager.
Best-effort: failures are logged but do not block the approval flow.
"""

import json
import os
import re
import base64
import traceback
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import boto3

GITHUB_API = 'https://api.github.com'

_github_token = None


def _get_github_token():
    """Retrieve the GitHub PAT from Secrets Manager (cached per Lambda invocation)."""
    global _github_token
    if _github_token is not None:
        return _github_token

    secret_name = os.environ.get('GITHUB_TOKEN_SECRET_NAME')
    if not secret_name:
        raise RuntimeError('GITHUB_TOKEN_SECRET_NAME not configured')

    client = boto3.client('secretsmanager')
    resp = client.get_secret_value(SecretId=secret_name)
    _github_token = resp['SecretString'].strip()
    return _github_token


def _github_request(method, path, body=None):
    """Make an authenticated request to the GitHub API."""
    token = _get_github_token()
    url = f'{GITHUB_API}{path}'
    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, method=method)
    req.add_header('Authorization', f'token {token}')
    req.add_header('Accept', 'application/vnd.github.v3+json')
    req.add_header('Content-Type', 'application/json')
    req.add_header('User-Agent', 'dctech-events-api')

    resp = urlopen(req)
    return json.loads(resp.read().decode())


def _slugify(text):
    """Convert text to a URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:60].rstrip('-')


def _to_yaml(fields, data):
    """Convert a dict to YAML string using the given field order."""
    lines = []
    for field in fields:
        val = data.get(field)
        if val is None or val == '':
            continue

        if field == 'categories' and isinstance(val, list) and val:
            lines.append('categories:')
            for cat in val:
                lines.append(f'  - {cat}')
        elif isinstance(val, dict):
            lines.append(f'{field}:')
            for k, v in val.items():
                lines.append(f"  '{k}': '{v}'")
        elif isinstance(val, bool):
            lines.append(f"{field}: {'true' if val else 'false'}")
        elif isinstance(val, str) and (':' in val or "'" in val or '"' in val or '\n' in val):
            escaped = val.replace("'", "''")
            lines.append(f"{field}: '{escaped}'")
        else:
            lines.append(f"{field}: '{val}'")

    return '\n'.join(lines) + '\n'


def _commit_file(file_path, content, message):
    """Commit a file to the GitHub repo. Returns commit URL or None."""
    owner = os.environ.get('GITHUB_REPO_OWNER', 'rosskarchner')
    repo = os.environ.get('GITHUB_REPO_NAME', 'dctech.events')

    try:
        encoded = base64.b64encode(content.encode()).decode()

        # Check if file already exists (to get its SHA for updates)
        sha = None
        try:
            existing = _github_request('GET', f'/repos/{owner}/{repo}/contents/{file_path}')
            sha = existing.get('sha')
        except HTTPError as e:
            if e.code != 404:
                raise

        body = {
            'message': message,
            'content': encoded,
            'branch': 'main',
        }
        if sha:
            body['sha'] = sha

        result = _github_request('PUT', f'/repos/{owner}/{repo}/contents/{file_path}', body)
        commit_url = result.get('commit', {}).get('html_url', '')
        print(f"Committed {file_path}: {commit_url}")
        return commit_url

    except Exception:
        print(f"ERROR committing {file_path} to GitHub: {traceback.format_exc()}")
        return None


EVENT_FIELDS = [
    'title', 'date', 'time', 'end_date', 'end_time',
    'url', 'location', 'cost', 'description',
    'categories', 'submitted_by',
]

GROUP_FIELDS = [
    'name', 'active', 'website', 'ical', 'fallback_url', 'categories',
]


def commit_event_to_repo(event_data, site='dctech'):
    """Commit an approved event as a YAML file to {site}/_single_events/."""
    date = event_data.get('date', 'unknown')
    title = event_data.get('title', 'event')
    slug = _slugify(title)
    file_path = f'{site}/_single_events/{date}-{slug}.yaml'
    yaml_content = _to_yaml(EVENT_FIELDS, event_data)
    message = f"Add event: {event_data.get('title', 'new event')}"
    return _commit_file(file_path, yaml_content, message)


def commit_group_to_repo(group_data, site='dctech'):
    """Commit an approved group as a YAML file to {site}/_groups/."""
    name = group_data.get('name', 'group')
    slug = _slugify(name)
    # Ensure active defaults to true for new groups
    data = {**group_data, 'active': True}
    # Map ical_url field to ical (form uses ical_url, YAML uses ical)
    if 'ical_url' in data and 'ical' not in data:
        data['ical'] = data.pop('ical_url')
    file_path = f'{site}/_groups/{slug}.yaml'
    yaml_content = _to_yaml(GROUP_FIELDS, data)
    message = f"Add group: {name}"
    return _commit_file(file_path, yaml_content, message)
