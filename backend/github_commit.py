"""
Commit approved events as YAML files to _single_events/ in the GitHub repo.

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


def _event_to_yaml(event_data):
    """Convert event dict to YAML string (hand-rolled to avoid PyYAML dependency)."""
    lines = []

    field_order = [
        'title', 'date', 'time', 'end_date', 'end_time',
        'url', 'location', 'cost', 'description',
        'categories', 'submitted_by',
    ]

    for field in field_order:
        val = event_data.get(field)
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


def _build_filename(event_data):
    """Build a _single_events/ filename from event data."""
    date = event_data.get('date', 'unknown')
    title = event_data.get('title', 'event')
    slug = _slugify(title)
    return f'_single_events/{date}-{slug}.yaml'


def commit_event_to_repo(event_data):
    """
    Commit an approved event as a YAML file to _single_events/ in the repo.

    Args:
        event_data: dict with event fields (title, date, time, url, etc.)

    Returns:
        The commit URL on success, or None on failure.
    """
    owner = os.environ.get('GITHUB_REPO_OWNER', 'rosskarchner')
    repo = os.environ.get('GITHUB_REPO_NAME', 'dctech.events')

    try:
        yaml_content = _event_to_yaml(event_data)
        file_path = _build_filename(event_data)
        encoded = base64.b64encode(yaml_content.encode()).decode()

        # Check if file already exists (to get its SHA for updates)
        sha = None
        try:
            existing = _github_request('GET', f'/repos/{owner}/{repo}/contents/{file_path}')
            sha = existing.get('sha')
        except HTTPError as e:
            if e.code != 404:
                raise

        body = {
            'message': f"Add event: {event_data.get('title', 'new event')}",
            'content': encoded,
            'branch': 'main',
        }
        if sha:
            body['sha'] = sha

        result = _github_request('PUT', f'/repos/{owner}/{repo}/contents/{file_path}', body)
        commit_url = result.get('commit', {}).get('html_url', '')
        print(f"Committed event to {file_path}: {commit_url}")
        return commit_url

    except Exception:
        print(f"ERROR committing event to GitHub: {traceback.format_exc()}")
        return None
