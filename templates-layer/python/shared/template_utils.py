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

def render_template(template_name, context=None):
    """
    Renders a mustache template with the provided context.
    
    Args:
        template_name: Name of the template file (relative to templates directory)
        context: Dictionary of context data for the template
    
    Returns:
        Rendered template content
    """
    try:
        # Default empty context if none provided
        if context is None:
            context = {}
            
        # Load the template
        template_path = os.path.join(os.path.dirname(__file__), '../templates', template_name)
        with open(template_path, 'r') as template_file:
            template_content = template_file.read()
        
        # Render the template with the context
        rendered_content = chevron.render(template_content, context)
        return rendered_content
    except Exception as e:
        logger.error(f"Error rendering template {template_name}: {str(e)}")
        return f"""
        <div class="error-message">
            <h2>Error</h2>
            <p>An error occurred while rendering the template: {str(e)}</p>
        </div>
        """

def enqueue_static_render(queue_url=None, template_name=None, output_path=None, context=None, page=None):
    """
    Enqueues a request to render a static page.
    
    Args:
        queue_url: URL of the SQS queue. If None, will try to get from RENDER_QUEUE_URL environment variable.
        template_name: Name of the template to render (used with output_path)
        output_path: Path where the rendered content should be stored (used with template_name)
        context: Dictionary of context data for the template
        page: Path to a page in the pages directory to render (alternative to template_name/output_path)
    
    Returns:
        SQS message ID or None if queue_url is not provided and not in environment
    """
    try:
        # If no queue URL is provided, try to get from environment
        if not queue_url:
            queue_url = os.environ.get('RENDER_QUEUE_URL')
            
        if not queue_url:
            logger.warning("No render queue URL provided or found in environment, skipping static render request")
            return None
            
        # Default empty context if none provided
        if context is None:
            context = {}
            
        # Create the message body
        message_body = {
            'timestamp': datetime.now().isoformat()
        }
        
        # Handle page-based rendering (from pages directory)
        if page:
            message_body['page'] = page
        # Handle template-based rendering (template to output path)
        elif template_name and output_path:
            message_body['template_name'] = template_name
            message_body['output_path'] = output_path
            message_body['context'] = context
        else:
            logger.error("Either 'page' or both 'template_name' and 'output_path' must be provided")
            return None
        
        # Send the message to the queue
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message_body)
        )
        
        if page:
            logger.info(f"Enqueued render request for page {page}: {response['MessageId']}")
        else:
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

def parse_form_data(event):
    """
    Parses form data from an API Gateway event.
    
    Args:
        event: API Gateway event
    
    Returns:
        Dictionary of form data
    """
    try:
        # Get the body from the event
        body = event.get('body', '')
        
        # Check if the body is base64 encoded
        is_base64_encoded = event.get('isBase64Encoded', False)
        if is_base64_encoded:
            import base64
            body = base64.b64decode(body).decode('utf-8')
        
        # Parse form-encoded data
        form_data = {}
        for pair in body.split('&'):
            if '=' in pair:
                key, value = pair.split('=', 1)
                # URL decode the values
                from urllib.parse import unquote
                form_data[key] = unquote(value)
        
        return form_data
    except Exception as e:
        logger.error(f"Error parsing form data: {str(e)}")
        return {}
