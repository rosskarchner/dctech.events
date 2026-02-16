"""
DynamoDB Stream Dispatcher

Receives DynamoDB stream events from the config table and sends a
rebuild trigger message to the SQS FIFO queue. Uses floor(epoch/60)
as the deduplication ID to batch rapid changes into a single rebuild.
"""

import json
import os
import time
import boto3

sqs = boto3.client('sqs')

REBUILD_QUEUE_URL = os.environ['REBUILD_QUEUE_URL']
DEDUP_WINDOW_SECONDS = int(os.environ.get('DEDUP_WINDOW_SECONDS', '60'))


def lambda_handler(event, context):
    """Process DynamoDB stream records and trigger rebuild."""
    records = event.get('Records', [])
    if not records:
        return {'batchItemFailures': []}

    # Calculate deduplication ID: floor(epoch / window)
    dedup_id = str(int(time.time() // DEDUP_WINDOW_SECONDS))

    # Collect changed entity types for logging
    changed_entities = set()
    for record in records:
        event_name = record.get('eventName', '')
        keys = record.get('dynamodb', {}).get('Keys', {})
        pk = keys.get('PK', {}).get('S', '')
        entity_type = pk.split('#')[0] if '#' in pk else pk
        changed_entities.add(f"{event_name}:{entity_type}")

    message_body = json.dumps({
        'trigger': 'dynamodb_stream',
        'timestamp': int(time.time()),
        'changed_entities': list(changed_entities),
        'record_count': len(records),
    })

    try:
        sqs.send_message(
            QueueUrl=REBUILD_QUEUE_URL,
            MessageBody=message_body,
            MessageGroupId='rebuild',
            MessageDeduplicationId=dedup_id,
        )
        print(f"Sent rebuild trigger (dedup_id={dedup_id}, changes={changed_entities})")
    except Exception as e:
        print(f"Error sending rebuild trigger: {e}")
        # Return all records as failed for retry
        return {
            'batchItemFailures': [
                {'itemIdentifier': r['eventID']} for r in records
            ]
        }

    return {'batchItemFailures': []}
