import json
import os
import boto3
import chevron
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize S3 client
s3 = boto3.client('s3')

def handler(event, context):
    """
    Lambda function to render mustache templates and write them to the render bucket.
    Currently renders hello.mustache to index.html.
    """
    try:
        # Get environment variables
        render_bucket = os.environ.get('RENDER_BUCKET')
        
        if not render_bucket:
            raise ValueError("RENDER_BUCKET environment variable is not set")
        
        # Log the event for debugging
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Load the shell template from the local templates directory
        with open('templates/shell.mustache', 'r') as shell_file:
            shell_template = shell_file.read()
        
        # Load the hello template from the local templates directory
        with open('templates/hello.mustache', 'r') as hello_file:
            hello_template = hello_file.read()
        
        # Render the hello template
        hello_content = hello_template  # Simple template doesn't need data
        
        # Prepare data for the shell template
        shell_data = {
            "title": "Welcome to DC Tech Events",
            "content": hello_content
        }
        
        # Render the shell template with the hello content
        rendered_content = chevron.render(shell_template, shell_data)
        
        # Write the rendered content to S3
        s3.put_object(
            Bucket=render_bucket,
            Key="index.html",
            Body=rendered_content,
            ContentType="text/html"
        )
        
        logger.info("Successfully rendered hello.mustache to index.html")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': "Successfully rendered hello.mustache to index.html",
                'bucket': render_bucket,
                'key': "index.html"
            })
        }
    
    except Exception as e:
        logger.error(f"Error in render function: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': f"Error rendering template: {str(e)}"
            })
        }
