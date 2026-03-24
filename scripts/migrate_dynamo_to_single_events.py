#!/usr/bin/env python3
"""
Migrate future events from DynamoDB (source=submitted|manual) to _single_events/ YAML files.

Usage:
    python scripts/migrate_dynamo_to_single_events.py [--dry-run]

Requires AWS credentials and boto3.
"""

import os
import re
import sys
import argparse

import boto3
from boto3.dynamodb.conditions import Key, Attr
from datetime import date


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:60].rstrip('-')


def event_to_yaml(event_data):
    """Convert event dict to YAML string."""
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


def main():
    parser = argparse.ArgumentParser(description='Migrate DynamoDB events to _single_events/')
    parser.add_argument('--dry-run', action='store_true', help='Print files without writing')
    parser.add_argument('--table', default='dctech-events', help='DynamoDB table name')
    args = parser.parse_args()

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(args.table)

    today = date.today().isoformat()
    response = table.query(
        IndexName='GSI4',
        KeyConditionExpression=Key('GSI4PK').eq('EVT#ACTIVE') & Key('GSI4SK').gte(today),
    )
    items = response.get('Items', [])
    while 'LastEvaluatedKey' in response:
        response = table.query(
            IndexName='GSI4',
            KeyConditionExpression=Key('GSI4PK').eq('EVT#ACTIVE') & Key('GSI4SK').gte(today),
            ExclusiveStartKey=response['LastEvaluatedKey'],
        )
        items.extend(response.get('Items', []))

    # Filter to submitted/manual events only
    manual_events = [
        item for item in items
        if item.get('source') in ('submitted', 'manual', 'config')
        and not item.get('hidden')
        and not item.get('duplicate_of')
    ]

    print(f"Found {len(manual_events)} future submitted/manual events out of {len(items)} total")

    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '_single_events')
    os.makedirs(output_dir, exist_ok=True)

    for item in manual_events:
        event_data = {}
        for field in ['title', 'date', 'time', 'end_date', 'end_time',
                      'url', 'location', 'cost', 'description',
                      'categories', 'submitted_by', 'city', 'state', 'all_day']:
            if field in item and item[field] is not None:
                val = item[field]
                # Convert Decimal to appropriate type
                if hasattr(val, '__float__'):
                    val = float(val)
                event_data[field] = val

        date_val = event_data.get('date', 'unknown')
        title = event_data.get('title', 'event')
        slug = slugify(title)
        filename = f"{date_val}-{slug}.yaml"
        filepath = os.path.join(output_dir, filename)

        yaml_content = event_to_yaml(event_data)

        if args.dry_run:
            print(f"\n--- {filename} ---")
            print(yaml_content)
        else:
            with open(filepath, 'w') as f:
                f.write(yaml_content)
            print(f"  Wrote {filename}")

    if not args.dry_run:
        print(f"\nWrote {len(manual_events)} files to {output_dir}/")


if __name__ == '__main__':
    main()
