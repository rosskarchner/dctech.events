import json
import os
import boto3
import chevron
import logging
from datetime import datetime
import pathlib
import time

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize S3 client
s3 = boto3.client('s3')
# Initialize CloudFront client
cloudfront = boto3.client('cloudfront')

def renderpage(template_path, shell_template, render_bucket):
    """
    Renders a mustache template and uploads both standalone and shell-wrapped versions to S3.
    
    Args:
        template_path: Path to the mustache template file
        shell_template: Content of the shell template
        render_bucket: S3 bucket to upload rendered files to
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
        
        # Render the template (without data for now)
        rendered_content = chevron.render(template_content, {})
        
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
            "title": "DC Tech Events",  # Default title
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

def handler(event, context):
    """
    Lambda function to render mustache templates and write them to the render bucket.
    Walks the pages directory tree and renders all .mustache files.
    """
    try:
        # Get environment variables
        render_bucket = os.environ.get('RENDER_BUCKET')
        distribution_id = os.environ.get('DISTRIBUTION_ID')
        
        if not render_bucket:
            raise ValueError("RENDER_BUCKET environment variable is not set")
        
        # Log the event for debugging
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Load the shell template from the local templates directory
        with open('templates/shell.mustache', 'r') as shell_file:
            shell_template = shell_file.read()
        
        # Walk the pages directory tree
        pages_dir = pathlib.Path('pages')
        rendered_files = []
        failed_files = []
        paths_to_invalidate = ['/*']  # Invalidate everything for simplicity
        
        # Find all .mustache files in the pages directory
        for template_path in pages_dir.glob('**/*.mustache'):
            logger.info(f"Processing template: {template_path}")
            success = renderpage(str(template_path), shell_template, render_bucket)
            
            if success:
                rendered_files.append(str(template_path))
            else:
                failed_files.append(str(template_path))
        
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
