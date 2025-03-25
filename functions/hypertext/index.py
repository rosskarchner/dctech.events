import json

def handler(event, context):
    # Get the path from the event
    path = event.get('pathParameters', {}).get('proxy', '')
    
    # Create a simple HTML response
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>DC Tech Events</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }}
            h1 {{ color: #333; }}
            form {{ margin: 20px 0; }}
            input[type="email"] {{ padding: 8px; width: 300px; margin-right: 10px; }}
            button {{ padding: 8px 16px; background-color: #0066cc; color: white; border: none; cursor: pointer; }}
            button:hover {{ background-color: #0055aa; }}
        </style>
    </head>
    <body>
        <h1>DC Tech Events</h1>
        <p>Stay updated with the latest tech events in the DC area!</p>
        
        <form action="/signup" method="POST">
            <input type="email" name="email" placeholder="Enter your email to subscribe" required>
            <button type="submit">Subscribe</button>
        </form>
        
        <p>You requested path: <strong>{path}</strong></p>
    </body>
    </html>
    """
    
    # Return the HTML response
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/html'
        },
        'body': html_content
    }
