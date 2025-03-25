import os
import json

def generate_form_html():
    """Generate HTML for the create source form"""
    return """
    <div id="create-source-form" class="create-source-form">
        <h2>Add New Source</h2>
        <form hx-post="/api/sources" hx-target="#adminFormContainer" hx-swap="outerHTML">
            <div class="form-group">
                <label for="organizationName">Organization Name:</label>
                <input type="text" id="organizationName" name="organizationName" required>
            </div>

            <div class="form-group">
                <label for="url">Website URL:</label>
                <input type="url" id="url" name="url" required 
                       placeholder="https://example.com">
            </div>

            <div class="form-group">
                <label for="icalUrl">iCal URL:</label>
                <input type="url" id="icalUrl" name="icalUrl" required
                       placeholder="https://example.com/events.ics">
            </div>

            <button type="submit">
                <span class="htmx-indicator">
                    <div class="loading-spinner"></div> Creating...
                </span>
                <span class="submit-text">Add Source</span>
            </button>
        </form>
    </div>
    """

def handler(event, context):
    try:
        # Since this endpoint is protected by an authorizer,
        # we can assume the user has admin permissions if they reach here
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Api-Key',
                'Access-Control-Allow-Methods': 'GET,POST',
            },
            'body': generate_form_html()
        }

    except Exception as e:
        print(f"Error generating form: {str(e)}")
        error_html = """
        <div class="error-message">
            <h3>Error</h3>
            <p>There was a problem loading the form. Please try again later.</p>
        </div>
        """
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'text/html',
                'Access-Control-Allow-Origin': '*',
            },
            'body': error_html
        }
