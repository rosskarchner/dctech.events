#!/bin/bash

# Script to run the aggregator lambda without arguments
# This will process all approved groups and update events

echo "Running aggregator lambda..."
curl -X POST "http://localhost:8080/2015-03-31/functions/function/invocations" -d '{}'
echo -e "\nAggregator run completed!"