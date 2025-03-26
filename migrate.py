#!/usr/bin/env python3
import boto3
import os
from datetime import datetime

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')

# Replace with your table name
SOURCES_TABLE_NAME = 'ApiStack-SourcesTable1DBF2A17-1KCZQ3V0ASIF1' # Replace with your actual table name

def migrate_sources():
    print(f"Starting migration of sources to new schema...")
    
    # Get the sources table
    sources_table = dynamodb.Table(SOURCES_TABLE_NAME)
    
    # Scan all existing sources
    response = sources_table.scan()
    sources = response.get('Items', [])
    
    # Continue scanning if we haven't got all items
    while 'LastEvaluatedKey' in response:
        response = sources_table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        sources.extend(response.get('Items', []))
    
    print(f"Found {len(sources)} sources to migrate")
    
    # Current timestamp for updated_at
    timestamp = datetime.utcnow().isoformat()
    
    # Update each source with the new fields
    for source in sources:
        source_id = source['id']
        
        # Skip if already migrated
        if 'approval_status' in source:
            print(f"Source {source_id} already migrated, skipping")
            continue
        
        print(f"Migrating source {source_id}: {source.get('name', 'Unknown')}")
        
        # Update with new fields
        sources_table.update_item(
            Key={'id': source_id},
            UpdateExpression='SET approval_status = :status, updated_at = :updated_at',
            ExpressionAttributeValues={
                ':status': 'approved',  # Set all existing sources as approved
                ':updated_at': timestamp
            }
        )
    
    print(f"Migration completed. {len(sources)} sources updated.")

if __name__ == "__main__":
    # Get table name from environment or use default
    table_name = os.environ.get('SOURCES_TABLE', SOURCES_TABLE_NAME)
    SOURCES_TABLE_NAME = table_name
    
    # Run migration
    migrate_sources()