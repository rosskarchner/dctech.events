#!/bin/bash

# lambda_function.sh - Lambda function for frontend container
# This script runs freeze.py and uploads the generated files to S3

# Function to handle Lambda invocation
function handle_lambda_invocation() {
    echo "Starting Lambda invocation..."
    
    # Run the freeze.py script to generate static files
    echo "Running freeze.py to generate static files..."
    cd /app
    python freeze.py
    
    # Check if freeze.py was successful
    if [ $? -ne 0 ]; then
        echo "Error: freeze.py failed to execute successfully."
        return 1
    fi
    
    # Determine S3 endpoint based on environment
    if [ "$ENVIRONMENT" == "local" ]; then
        S3_ENDPOINT="--endpoint-url $AWS_S3_ENDPOINT_URL"
        
        # Create bucket if it doesn't exist (only in local environment)
        echo "Checking if bucket exists: $S3_BUCKET_NAME"
        aws s3 ls s3://$S3_BUCKET_NAME $S3_ENDPOINT > /dev/null 2>&1
        if [ $? -ne 0 ]; then
            echo "Creating bucket: $S3_BUCKET_NAME"
            aws s3 mb s3://$S3_BUCKET_NAME $S3_ENDPOINT
            
            # Configure bucket for website hosting
            aws s3 website s3://$S3_BUCKET_NAME $S3_ENDPOINT --index-document index.html --error-document 404.html
        fi
    else
        S3_ENDPOINT=""
    fi
    
    # Upload the build directory to S3
    echo "Uploading build directory to S3 bucket: $S3_BUCKET_NAME"
    aws s3 sync /app/build/ s3://$S3_BUCKET_NAME/ $S3_ENDPOINT --acl public-read
    
    # Check if upload was successful
    if [ $? -ne 0 ]; then
        echo "Error: Failed to upload build directory to S3."
        return 1
    fi
    
    echo "Lambda invocation completed successfully."
    return 0
}

# Execute the Lambda function
handle_lambda_invocation
exit $?