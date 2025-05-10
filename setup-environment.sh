#!/bin/bash

# Script to set up the complete environment
# This script will reset tables, load sample groups, and run the aggregator

echo "Setting up the complete environment..."

# Step 1: Reset tables
echo "Step 1: Resetting tables..."
./reset-tables.sh

# Step 2: Load sample groups
echo "Step 2: Loading sample groups..."
./load-sample-groups.sh

# Step 3: Run the aggregator
echo "Step 3: Running the aggregator..."
./run-aggregator.sh

echo "Environment setup complete!"