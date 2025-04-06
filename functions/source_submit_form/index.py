import os
import json
import boto3
from datetime import datetime, timedelta

def generate_form_html():
    """Generate HTML for the source submission form"""
    return """
    <div id="source-form">
        <p>
            Do you know of an organization that hosts tech events in DC and has an iCal feed?
            Submit it here for inclusion in our calendar.
        </p>
        
        <form id="submit-source-form" 
              hx-post="/api/submit-source" 
              hx-target="#source-form" 
              hx-swap="innerHTML"
              hx-indicator="#submit-spinner">
            <div class="form-group">
                <label for="name">Organization Name:</label>
                <input type="text" id="name" name="name" required>
            </div>
            
            <div class="form-group">
                <label for="website">Website URL:</label>
                <input type="url" id="website" name="website" placeholder="https://example.com">
                <small>The organization's main website</small>
            </div>
            
            <div class="form-group">
                <label for="ical_url">iCal URL:</label>
                <input type="url" id="ical_url" name="ical_url" required placeholder="https://example.com/events.ics">
                <small>This should be a direct link to an iCal feed of events</small>
            </div>
            
            <button type="submit">
                <span id="submit-spinner" class="htmx-indicator">Submitting...</span>
                <span>Submit Source</span>
            </button>
        </form>
        
        <div id="result"></div>
    </div>
    """

def handler(event, context):

            
            response = {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'text/html',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Api-Key',
                    'Access-Control-Allow-Methods': 'GET,POST',
                },
                'body': generate_form_html()
            }
            
 
            
            return response
                

        