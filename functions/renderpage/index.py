import json
import os
import boto3
import chevron
import logging
from datetime import datetime
import pathlib
import time
from shared.template_utils import prepare_group_for_template

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize S3 client
s3 = boto3.client('s3')
# Initialize CloudFront client
cloudfront = boto3.client('cloudfront')
# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')

def renderpage(template_path, shell_template, render_bucket, context=None):
    """
    Renders a mustache template and uploads both standalone and shell-wrapped versions to S3.
    
    Args:
        template_path: Path to the mustache template file
        shell_template: Content of the shell template
        render_bucket: S3 bucket to upload rendered files to
        context: Optional context data for template rendering
    """
    try:
        # Read the template file
        with open(template_path, 'r') as template_file:
            template_content = template_file.read()
        
        # Get the relative path from the pages directory
        rel_path = os.path.relpath(template_path, 'pages')
        
        # Replace .mustache extension with .html
        html_path = os.path.splitext(rel_path)[0] + '.html'
        
        # If the file is named index.mustache, the output should be in the directory
        # Otherwise, use the full path
        if os.path.basename(html_path) == 'index.html':
            output_path = os.path.dirname(html_path)
            if output_path == '':
                output_path = 'index.html'
            else:
                output_path = f"{output_path}/index.html"
        else:
            output_path = html_path
        
        # Use empty context if none provided
        if context is None:
            context = {}
        
        # Render the template with the context
        rendered_content = chevron.render(template_content, context)
        
        # Upload the standalone version to /hx/path.html
        hx_key = f"hx/{output_path}"
        s3.put_object(
            Bucket=render_bucket,
            Key=hx_key,
            Body=rendered_content,
            ContentType="text/html"
        )
        logger.info(f"Uploaded standalone version to {hx_key}")
        
        # Prepare data for the shell template
        shell_data = {
            "title": context.get("title", "DC Tech Events"),  # Use title from context if available
            "content": rendered_content
        }
        
        # Render the shell template with the content
        full_rendered_content = chevron.render(shell_template, shell_data)
        
        # Upload the shell-wrapped version to /path.html
        s3.put_object(
            Bucket=render_bucket,
            Key=output_path,
            Body=full_rendered_content,
            ContentType="text/html"
        )
        logger.info(f"Uploaded shell-wrapped version to {output_path}")
        
        return True
    except Exception as e:
        logger.error(f"Error rendering {template_path}: {str(e)}")
        return False

def create_invalidation(distribution_id, paths):
    """
    Creates a CloudFront invalidation for the specified paths.
    
    Args:
        distribution_id: CloudFront distribution ID
        paths: List of paths to invalidate
    
    Returns:
        Invalidation ID
    """
    try:
        if not distribution_id:
            logger.warning("No distribution ID provided, skipping invalidation")
            return None
            
        # Create the invalidation
        response = cloudfront.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                'Paths': {
                    'Quantity': len(paths),
                    'Items': paths
                },
                'CallerReference': str(time.time())
            }
        )
        
        invalidation_id = response['Invalidation']['Id']
        logger.info(f"Created invalidation {invalidation_id} for paths: {paths}")
        return invalidation_id
    except Exception as e:
        logger.error(f"Error creating invalidation: {str(e)}")
        return None

def get_approved_groups():
    """
    Queries the DynamoDB table for approved groups.
    
    Returns:
        List of approved groups
    """
    try:
        # Get the groups table name from environment variable
        groups_table_name = os.environ.get('GROUPS_TABLE')
        if not groups_table_name:
            logger.warning("GROUPS_TABLE environment variable is not set")
            return []
        
        # Initialize the groups table
        groups_table = dynamodb.Table(groups_table_name)
        
        # Query the groups table for approved groups
        response = groups_table.scan(
            FilterExpression="approval_status = :status",
            ExpressionAttributeValues={
                ":status": "approved"
            }
        )
        
        # Get the groups from the response
        groups = response.get('Items', [])
        
        # Sort groups by name
        groups.sort(key=lambda x: x.get('name', '').lower())
        
        # Prepare groups for template rendering
        prepared_groups = [prepare_group_for_template(group) for group in groups]
        
        return prepared_groups
    except Exception as e:
        logger.error(f"Error getting approved groups: {str(e)}")
        return []

def handler(event, context):
    """
    Lambda function to render mustache templates and write them to the render bucket.
    Can either:
    1. Walk the pages directory tree and render all .mustache files (default behavior)
    2. Render a specific page from the pages directory (if specified in the event)
    3. Render a particular template to a particular path with provided context
    """
    try:
        # Get environment variables
        render_bucket = os.environ.get('RENDER_BUCKET')
        distribution_id = os.environ.get('DISTRIBUTION_ID')
        
        if not render_bucket:
            raise ValueError("RENDER_BUCKET environment variable is not set")
        
        # Log the event for debugging
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Load the shell template from the templates layer
        shell_template_path = os.path.join('/opt/python/templates', 'shell.mustache')
        with open(shell_template_path, 'r') as shell_file:
            shell_template = shell_file.read()
        
        rendered_files = []
        failed_files = []
        paths_to_invalidate = []
        
        # Check if this is an SQS event
        if 'Records' in event and len(event['Records']) > 0:
            for record in event['Records']:
                if record.get('eventSource') == 'aws:sqs':
                    # Process SQS message
                    message_body = json.loads(record['body'])
                    logger.info(f"Processing SQS message: {json.dumps(message_body)}")
                    
                    # Check if this is a request to render a specific page
                    if 'page' in message_body:
                        page_path = message_body['page']
                        # Remove leading slash if present
                        if page_path.startswith('/'):
                            page_path = page_path[1:]
                            
                        # Convert to mustache path in pages directory
                        if page_path.endswith('.html'):
                            page_path = page_path[:-5] + '.mustache'
                        
                        template_path = pathlib.Path('pages') / page_path
                        
                        logger.info(f"Rendering specific page: {template_path}")
                        
                        if not template_path.exists():
                            logger.error(f"Template not found: {template_path}")
                            failed_files.append(str(template_path))
                            continue
                        
                        # Check if this is a special template that needs data
                        template_str = str(template_path)
                        context = None
                        
                        # Handle groups list page
                        if 'groups/index.mustache' in template_str:
                            logger.info("Rendering groups list page with data")
                            groups = get_approved_groups()
                            context = {
                                'title': 'Tech Groups in DC',
                                'groups': groups
                            }
                        
                        # Render the template with the appropriate context
                        success = renderpage(template_str, shell_template, render_bucket, context)
                        
                        if success:
                            rendered_files.append(template_str)
                            # Add specific path to invalidation list
                            output_path = '/' + page_path.replace('.mustache', '.html')
                            paths_to_invalidate.append(output_path)
                            paths_to_invalidate.append('/hx' + output_path)
                        else:
                            failed_files.append(template_str)
                    
                    # Handle template_name and output_path with context
                    elif 'template_name' in message_body and 'output_path' in message_body:
                        template_name = message_body['template_name']
                        output_path = message_body['output_path']
                        template_context = message_body.get('context', {})
                        
                        logger.info(f"Rendering template {template_name} to {output_path}")
                        
                        # Load the template from the templates layer
                        template_path = os.path.join('/opt/python/templates', template_name)
                        
                        if not os.path.exists(template_path):
                            logger.error(f"Template not found: {template_path}")
                            failed_files.append(template_name)
                            continue
                        
                        # Read the template file
                        with open(template_path, 'r') as template_file:
                            template_content = template_file.read()
                        
                        # Render the template with the context
                        rendered_content = chevron.render(template_content, template_context)
                        
                        # Upload the standalone version
                        hx_key = f"hx{output_path}"
                        s3.put_object(
                            Bucket=render_bucket,
                            Key=hx_key,
                            Body=rendered_content,
                            ContentType="text/html"
                        )
                        
                        # Prepare data for the shell template
                        shell_data = {
                            "title": template_context.get("title", "DC Tech Events"),
                            "content": rendered_content
                        }
                        
                        # Render the shell template with the content
                        full_rendered_content = chevron.render(shell_template, shell_data)
                        
                        # Upload the shell-wrapped version
                        # Remove leading slash if present
                        if output_path.startswith('/'):
                            output_path = output_path[1:]
                            
                        s3.put_object(
                            Bucket=render_bucket,
                            Key=output_path,
                            Body=full_rendered_content,
                            ContentType="text/html"
                        )
                        
                        rendered_files.append(template_name)
                        paths_to_invalidate.append('/' + output_path)
                        paths_to_invalidate.append('/hx/' + output_path)
                        
                    else:
                        logger.warning(f"Unrecognized message format: {json.dumps(message_body)}")
            
            # If no specific paths were invalidated, invalidate everything
            if not paths_to_invalidate:
                paths_to_invalidate = ['/*']
                
        else:
            # Default behavior: walk the pages directory tree and render all templates
            logger.info("No specific page requested, rendering all templates")
            paths_to_invalidate = ['/*']  # Invalidate everything
            
            # Find all .mustache files in the pages directory
            pages_dir = pathlib.Path('pages')
            for template_path in pages_dir.glob('**/*.mustache'):
                logger.info(f"Processing template: {template_path}")
                
                # Check if this is a special template that needs data
                template_str = str(template_path)
                context = None
                
                # Handle groups list page
                if 'groups/index.mustache' in template_str:
                    logger.info("Rendering groups list page with data")
                    groups = get_approved_groups()
                    context = {
                        'title': 'Tech Groups in DC',
                        'groups': groups
                    }
                
                # Render the template with the appropriate context
                success = renderpage(template_str, shell_template, render_bucket, context)
                
                if success:
                    rendered_files.append(template_str)
                else:
                    failed_files.append(template_str)
        
        # Create CloudFront invalidation if distribution ID is provided
        invalidation_id = None
        if distribution_id:
            invalidation_id = create_invalidation(distribution_id, paths_to_invalidate)
        
        # Return the results
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f"Rendered {len(rendered_files)} templates, {len(failed_files)} failed",
                'rendered': rendered_files,
                'failed': failed_files,
                'bucket': render_bucket,
                'invalidation': {
                    'distribution_id': distribution_id,
                    'invalidation_id': invalidation_id,
                    'paths': paths_to_invalidate
                }
            })
        }
    
    except Exception as e:
        logger.error(f"Error in render function: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': f"Error rendering templates: {str(e)}"
            })
        }
