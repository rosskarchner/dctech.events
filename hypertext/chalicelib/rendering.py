import os
import sys
import chevron

from chalice import Chalice, Response

# Get the absolute path to the templates directory
# Handle both local development and Lambda deployment scenarios
if getattr(sys, 'frozen', False):
    # Running in a Lambda deployment
    TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
else:
    # Running locally
    TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')


def render_template(app, template_name, code=200, **context):
    """
    Render a template with the given context
    
    If the request comes from HTMX, only render the template fragment.
    Otherwise, wrap the fragment in the shell template.
    """
    # Check if this is an HTMX request
    is_htmx = app.current_request.headers.get('HX-Request', 'false').lower() == 'true'
    
    try:
        # First render the main template
        template_path = os.path.join(TEMPLATE_DIR, template_name)
        print(f"Rendering template: {template_path}")
        print(f"Template exists: {os.path.exists(template_path)}")
        
        with open(template_path, 'r') as template_file:
            print(f"Template content: {template_file.read()[:100]}...")
            template_file.seek(0)  # Reset file pointer to beginning
            rendered_content = chevron.render(template_file, context)
        
        print(f"Rendered content length: {len(rendered_content)}")
        print(f"Rendered content preview: {rendered_content[:100]}...")
        
        # If this is an HTMX request, return just the fragment
        if is_htmx:
            return Response(
                body=rendered_content,
                status_code=code,
                headers={'Content-Type': 'text/html'}
            )
        
        # Otherwise, wrap it in the shell template
        shell_path = os.path.join(TEMPLATE_DIR, 'shell.mustache')
        print(f"Shell template path: {shell_path}")
        print(f"Shell template exists: {os.path.exists(shell_path)}")
        
        with open(shell_path, 'r') as shell_file:
            # Add the rendered content to the context for the shell
            shell_context = {
                'title': context.get('title', 'DC Tech Events'),
                'content': rendered_content
            }
            rendered_page = chevron.render(shell_file, shell_context)
            
        print(f"Final rendered page length: {len(rendered_page)}")
        
        return Response(
            body=rendered_page,
            status_code=code,
            headers={'Content-Type': 'text/html'}
        )
        
    except FileNotFoundError as e:
        print(f"Template not found: {e}")
        print(f"Current directory: {os.getcwd()}")
        print(f"Directory contents: {os.listdir(os.getcwd())}")
        if os.path.exists(TEMPLATE_DIR):
            print(f"Template dir contents: {os.listdir(TEMPLATE_DIR)}")
        else:
            print(f"Template dir does not exist: {TEMPLATE_DIR}")
        return Response(
            body="Template not found",
            status_code=500,
            headers={'Content-Type': 'text/plain'}
        )
    except Exception as e:
        print(f"Error rendering template: {str(e)}")
        return Response(
            body=f"Error rendering template: {str(e)}",
            status_code=500,
            headers={'Content-Type': 'text/plain'}
        )
