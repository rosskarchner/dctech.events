import os
import subprocess
import boto3
import logging
import json
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def run_command(command):
    """Run a shell command and return the output"""
    try:
        logger.info(f"Running command: {command}")
        result = subprocess.run(command, shell=True, check=True, 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                               universal_newlines=True)
        logger.info(f"Command output: {result.stdout}")
        if result.stderr:
            logger.warning(f"Command stderr: {result.stderr}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}")
        logger.error(f"Error output: {e.stderr}")
        return False

def generate_static_site():
    """Run freeze.py to generate static files"""
    logger.info("Starting static site generation...")
    
    # Change to the app directory
    os.chdir('/app')
    
    # Run freeze.py
    if not run_command('python freeze.py'):
        logger.error("Failed to generate static site")
        return False
    
    logger.info("Static site generation completed successfully")
    return True

def upload_to_s3():
    """Upload the build directory to S3"""
    logger.info("Starting S3 upload...")
    
    bucket_name = os.environ.get('S3_BUCKET_NAME')
    if not bucket_name:
        logger.error("S3_BUCKET_NAME environment variable not set")
        return False
    
    # Initialize S3 client
    s3_endpoint_url = os.environ.get('AWS_S3_ENDPOINT_URL')
    s3_client_args = {}
    
    if os.environ.get('ENVIRONMENT') == 'local' and s3_endpoint_url:
        s3_client_args['endpoint_url'] = s3_endpoint_url
        
        # Check if bucket exists, create if it doesn't
        try:
            s3_client = boto3.client('s3', **s3_client_args)
            s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"Bucket {bucket_name} exists")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.info(f"Creating bucket {bucket_name}")
                s3_client.create_bucket(Bucket=bucket_name)
                
                # Configure bucket for website hosting
                s3_client.put_bucket_website(
                    Bucket=bucket_name,
                    WebsiteConfiguration={
                        'IndexDocument': {'Suffix': 'index.html'},
                        'ErrorDocument': {'Key': '404.html'}
                    }
                )
            else:
                logger.error(f"Error checking bucket: {str(e)}")
                return False
    
    # Use AWS CLI for sync as it handles directories well
    sync_command = f"aws s3 sync /app/build/ s3://{bucket_name}/"
    
    if os.environ.get('ENVIRONMENT') == 'local' and s3_endpoint_url:
        sync_command += f" --endpoint-url {s3_endpoint_url}"
    
    # Add ACL for public read access
    sync_command += " --acl public-read"
    
    if not run_command(sync_command):
        logger.error("Failed to upload to S3")
        return False
    
    logger.info(f"Successfully uploaded build directory to S3 bucket: {bucket_name}")
    return True

def lambda_handler(event, context):
    """Lambda handler function - used by the aggregator function"""
    logger.info("Starting Lambda invocation...")
    logger.info(f"Event: {json.dumps(event)}")
    
    # Default handler for the aggregator function
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Aggregator function executed successfully'})
    }

def static_site_generator_handler(event, context):
    """Handler for the static site generator function"""
    logger.info("Starting static site generator invocation...")
    logger.info(f"Event: {json.dumps(event)}")
    
    # Check if this is a specific action
    if isinstance(event, dict) and event.get('action') == 'generate-static-site':
        if not generate_static_site():
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to generate static site'})
            }
        
        if not upload_to_s3():
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to upload to S3'})
            }
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Static site generated and uploaded successfully'})
        }
    
    return {
        'statusCode': 400,
        'body': json.dumps({'error': 'Invalid action specified'})
    }

def api_handler(event, context):
    """Handler for the API function"""
    logger.info("Starting API handler invocation...")
    logger.info(f"Event: {json.dumps(event)}")
    
    # For API Gateway requests, use awsgi to handle Flask app
    try:
        from app import app
        import awsgi
        
        return awsgi.response(app, event, context)
    except Exception as e:
        logger.error(f"Error handling API request: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }