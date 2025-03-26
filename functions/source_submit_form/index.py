import os
import json
import boto3

cognito = boto3.client('cognito-idp')

def generate_form_html():
    """Generate HTML for the source submission form"""
    return """
    <div id="source-form">
        <p>
            Do you know of an organization that hosts tech events in DC and has an iCal feed?
            Submit it here for inclusion in our calendar.
        </p>
        
        <form id="submit-source-form">
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
                <span id="submit-spinner" style="display: none;">Submitting...</span>
                <span id="submit-text">Submit Source</span>
            </button>
        </form>
        
        <div id="result"></div>
        
        <script>
            // Explicitly prevent default form submission
            document.getElementById('submit-source-form').addEventListener('submit', function(e) {
                e.preventDefault(); // This is crucial
                console.log('Form submission intercepted');
                
                // Show spinner
                document.getElementById('submit-spinner').style.display = 'inline';
                document.getElementById('submit-text').style.display = 'none';
                
                // Get form data
                const formData = new FormData(this);
                const formObject = {};
                formData.forEach((value, key) => {
                    formObject[key] = value;
                });
                
                // Get auth token
                const token = localStorage.getItem('authToken');
                
                // Use HTMX API directly
                htmx.ajax('POST', '/api/submit-source', {
                    source: this,
                    target: '#result',
                    swap: 'innerHTML',
                    values: formObject,
                    headers: {
                        'Authorization': 'Bearer ' + token,
                        'Content-Type': 'application/json'
                    }
                });
                
                return false;
            });
            
            // Debug HTMX events
            document.addEventListener('htmx:beforeRequest', function(evt) {
                console.log('HTMX Request:', evt.detail);
            });
            
            document.addEventListener('htmx:afterRequest', function(evt) {
                console.log('HTMX Response:', evt.detail);
                // Hide spinner
                document.getElementById('submit-spinner').style.display = 'none';
                document.getElementById('submit-text').style.display = 'inline';
            });
            
            document.addEventListener('htmx:responseError', function(evt) {
                console.log('HTMX Error:', evt.detail);
                // Hide spinner
                document.getElementById('submit-spinner').style.display = 'none';
                document.getElementById('submit-text').style.display = 'inline';
                
                document.getElementById('result').innerHTML = `
                    <div class="error-message">
                        <h3>Error</h3>
                        <p>There was a problem submitting the form. Please try again.</p>
                        <p>Error: ${evt.detail.error}</p>
                    </div>
                `;
            });
        </script>
    </div>
    """

def handler(event, context):
    try:
        print("Source submission form request received")
        print(f"Event: {json.dumps(event, default=str)}")
        
        # Check if user is authenticated
        if 'authorizer' not in event['requestContext'] or 'jwt' not in event['requestContext']['authorizer']:
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'text/html'},
                'body': """
                    <div class="auth-required">
                        <p>You must be logged in to submit sources.</p>
                        <a href="/login?redirect=/sources/submit" class="button">Login</a>
                    </div>
                """
            }
        
        # Get user ID from the request context
        user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']
        print(f"User ID: {user_id}")
        
        # Get user profile information
        user_pool_id = os.environ['USER_POOL_ID']
        
        try:
            user_response = cognito.admin_get_user(
                UserPoolId=user_pool_id,
                Username=user_id
            )
            
            # Extract user attributes
            user_attrs = {}
            for attr in user_response.get('UserAttributes', []):
                user_attrs[attr['Name']] = attr['Value']
            
            # Try different attribute names for name
            submitter_name = user_attrs.get('name', 
                            user_attrs.get('custom:name', 
                            user_attrs.get('custom:nickname', '')))
            
            # Check if profile is complete (has a name)
            if not submitter_name:
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'text/html'},
                    'body': """
                        <div class="auth-required">
                            <p>You need to complete your profile before submitting sources.</p>
                            <a href="/profile" class="button">Complete Profile</a>
                        </div>
                    """
                }
            
            # User is authenticated and has a complete profile, return the form
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
            print(f"Error getting user profile: {str(e)}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'text/html'},
                'body': f"""
                    <div class="error-message">
                        <p>Error retrieving user profile: {str(e)}</p>
                        <p>Please try again later.</p>
                    </div>
                """
            }
            
    except Exception as e:
        print(f"Error generating form: {str(e)}")
        error_html = f"""
        <div class="error-message">
            <h3>Error</h3>
            <p>There was a problem loading the form: {str(e)}</p>
            <p>Please try again later.</p>
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
