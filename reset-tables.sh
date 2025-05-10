#!/bin/bash

# Script to delete and recreate the DynamoDB tables
# This script will delete and recreate both LOCAL_GROUPS and LOCAL_EVENTS tables

echo "Deleting existing tables..."
aws dynamodb delete-table --table-name LOCAL_GROUPS --endpoint-url http://localhost:8000 || true
aws dynamodb delete-table --table-name LOCAL_EVENTS --endpoint-url http://localhost:8000 || true

echo "Waiting for tables to be deleted..."
sleep 2

echo "Creating tables..."
# Create LOCAL_GROUPS table
aws dynamodb create-table \
    --table-name LOCAL_GROUPS \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
        AttributeName=approval_status,AttributeType=S \
        AttributeName=organization_name,AttributeType=S \
    --key-schema \
        AttributeName=id,KeyType=HASH \
    --global-secondary-indexes \
        "[{
            \"IndexName\": \"approval-status-index\",
            \"KeySchema\": [{\"AttributeName\":\"approval_status\",\"KeyType\":\"HASH\"},
                           {\"AttributeName\":\"organization_name\",\"KeyType\":\"RANGE\"}],
            \"Projection\": {\"ProjectionType\":\"ALL\"}
        }]" \
    --billing-mode PAY_PER_REQUEST \
    --endpoint-url http://localhost:8000

# Create LOCAL_EVENTS table
aws dynamodb create-table \
    --table-name LOCAL_EVENTS \
    --attribute-definitions \
        AttributeName=week,AttributeType=S \
        AttributeName=sort,AttributeType=S \
        AttributeName=status,AttributeType=S \
        AttributeName=date,AttributeType=S \
        AttributeName=sourceId,AttributeType=S \
        AttributeName=id,AttributeType=S \
    --key-schema \
        AttributeName=week,KeyType=HASH \
        AttributeName=sort,KeyType=RANGE \
    --global-secondary-indexes \
        "[{
            \"IndexName\": \"status-index\",
            \"KeySchema\": [{\"AttributeName\":\"status\",\"KeyType\":\"HASH\"},
                           {\"AttributeName\":\"date\",\"KeyType\":\"RANGE\"}],
            \"Projection\": {\"ProjectionType\":\"ALL\"}
        },
        {
            \"IndexName\": \"group-index\",
            \"KeySchema\": [{\"AttributeName\":\"sourceId\",\"KeyType\":\"HASH\"},
                           {\"AttributeName\":\"id\",\"KeyType\":\"RANGE\"}],
            \"Projection\": {\"ProjectionType\":\"ALL\"}
        }]" \
    --billing-mode PAY_PER_REQUEST \
    --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES \
    --endpoint-url http://localhost:8000

echo "Tables created successfully!"