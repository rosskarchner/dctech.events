#!/bin/bash

# Script to load sample groups into the DynamoDB table
# This script invokes the aggregator lambda with the load-samples action

echo "Loading sample groups into DynamoDB..."
curl -X POST "http://localhost:8080/2015-03-31/functions/function/invocations" -d '{"action":"load-samples"}'
echo -e "\nSample groups loaded successfully!"