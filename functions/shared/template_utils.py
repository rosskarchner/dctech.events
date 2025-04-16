import os
import json
import boto3
import chevron
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize SQS client
sqs = boto3.client('sqs')

def render_template(template_path, context=None):
    """
    Renders a mustache template with the provided context.
    
    Args:
        template_path: Path to the template file
        context: Dictionary of context data for the template
    
    Returns:
        Rendered template content
    """
    try:
        # Default empty context if none provided
        if context is None:
            context = {}
            
        # Load the template
        with open(template_path, 'r') as template_file:
            template_content = template_file.read()
        
        # Render the template with the context
        rendered_content = chevron.render(template_content, context)
        return rendered_content
    except Exception as e:
        logger.error(f"Error rendering template {template_path}: {str(e)}")
        return f"""
        <div class="error-message">
            <h2>Error</h2>
            <p>An error occurred while rendering the template: {str(e)}</p>
        </div>
        """

def enqueue_static_render(queue_url, template_name, output_path, context=None):
    """
    Enqueues a request to render a static page.
    
    Args:
        queue_url: URL of the SQS queue
        template_name: Name of the template to render
        output_path: Path where the rendered content should be stored
        context: Dictionary of context data for the template
    
    Returns:
        SQS message ID or None if queue_url is not provided
    """
    try:
        # If no queue URL is provided, log a warning and return
        if not queue_url:
            logger.warning("No render queue URL provided, skipping static render request")
            return None
            
        # Default empty context if none provided
        if context is None:
            context = {}
            
        # Create the message body
        message_body = {
            'template_name': template_name,
            'output_path': output_path,
            'context': context,
            'timestamp': datetime.now().isoformat()
        }
        
        # Send the message to the queue
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message_body)
        )
        
        logger.info(f"Enqueued static render request for {template_name} to {output_path}: {response['MessageId']}")
        return response['MessageId']
    except Exception as e:
        logger.error(f"Error enqueuing static render request: {str(e)}")
        return None

def prepare_group_for_template(group):
    """
    Prepares a group object for template rendering by adding helper flags.
    
    Args:
        group: Group data dictionary
    
    Returns:
        Group with additional template helper flags
    """
    # Add flags for conditional rendering
    group['is_pending'] = group.get('approval_status') == 'pending'
    group['is_approved'] = group.get('approval_status') == 'approved'
    group['has_fallback_url'] = bool(group.get('fallback_url'))
    return group
