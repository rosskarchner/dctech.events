import awsgi
import json
from app import app

def handler(event, context):
    print(event)
    # Get the response from awsgi
    response = awsgi.response(app, event, context)
    print(json.dumps(response))
    return response