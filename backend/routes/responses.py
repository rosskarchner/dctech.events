"""Shared HTTP response builders for Lambda route handlers."""

import json as _json

ALLOWED_ORIGINS = [
    'https://dctech.events',
    'https://www.dctech.events',
    'http://localhost:5000',
]


def _origin(event):
    origin = (event or {}).get('headers', {}).get('origin')
    return origin if origin in ALLOWED_ORIGINS else ALLOWED_ORIGINS[0]


def html(status_code, body, event=None):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'text/html; charset=utf-8',
            'Access-Control-Allow-Origin': _origin(event),
            'Vary': 'Origin',
        },
        'body': body,
    }


def json(status_code, body, event=None):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': _origin(event),
            'Vary': 'Origin',
        },
        'body': _json.dumps(body),
    }
