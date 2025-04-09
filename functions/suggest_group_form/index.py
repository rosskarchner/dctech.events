def handler(event, context):
    """
    Returns the HTML form for suggesting a group.
    Authentication is handled by API Gateway authorizer.
    """
    # Get user information from the JWT claims
    jwt_claims = event['requestContext']['authorizer']['jwt']['claims']
    user_email = jwt_claims.get('email', 'User')
    
    # Create the HTML form
    html_form = f"""
    <form id="group-form" hx-post="https://api.dctech.events/api/groups" hx-swap="outerHTML">
        <p>Hello {user_email}, please provide details about the tech group you'd like to suggest.</p>
        
        <div class="form-group">
            <label for="group-name">Group Name *</label>
            <input type="text" id="group-name" name="name" required>
            <div class="error-message" id="name-error">Please enter a valid group name</div>
        </div>
        
        <div class="form-group">
            <label for="website-url">Website URL *</label>
            <input type="url" id="website-url" name="website" required placeholder="https://example.com">
            <div class="error-message" id="website-error">Please enter a valid URL</div>
        </div>
        
        <div class="form-group">
            <label for="ical-url">iCal URL *</label>
            <input type="url" id="ical-url" name="ical" required placeholder="https://example.com/events.ics">
            <div class="error-message" id="ical-error">Please enter a valid URL</div>
        </div>
        
        <button type="submit">Submit Group</button>
    </form>
    
    <style>
        .form-group {{
            margin-bottom: 20px;
        }}
        label {{
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }}
        input[type="text"], input[type="url"] {{
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 16px;
        }}
        button {{
            background-color: #0066cc;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            font-size: 16px;
            cursor: pointer;
        }}
        button:hover {{
            background-color: #0055aa;
        }}
        .error-message {{
            color: #d32f2f;
            margin-top: 5px;
            display: none;
        }}
    </style>
    """
    
    # Return the HTML form
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/html'
        },
        'body': html_form
    }
