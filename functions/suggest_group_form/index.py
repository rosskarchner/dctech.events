from shared.template_utils import render_template

def handler(event, context):
    """
    Returns the HTML form for suggesting a group.
    Authentication is handled by API Gateway authorizer.
    """
    # Get user information from the JWT claims
    jwt_claims = event['requestContext']['authorizer']['jwt']['claims']
    user_email = jwt_claims.get('email', 'User')
    
    # Render the template with the user's email
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/html'
        },
        'body': render_template('group_suggest_form.mustache', {
            'user_email': user_email
        })
    }
