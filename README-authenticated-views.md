# Authenticated User Views

This component provides a Flask application that handles authenticated user views, including event submission forms.

## Local Development

The authenticated-user-views service is configured in the docker-compose.yaml file and can be started along with the other services:

```bash
docker-compose up
```

The service will be available at:
- http://localhost:5001 (direct access to the Flask app)

## Structure

- `app.py` - The Flask application
- `lambda_function.py` - The Lambda handler that uses awsgi to serve the Flask app in production
- `requirements.txt` - Dependencies for the application
- `Dockerfile` - Multi-stage container configuration for both local development and Lambda deployment
- `templates/` - HTML templates for the application
- `static/` - Static assets for the application

## Integration with Frontend

The frontend application loads the event submission form from the authenticated-user-views service using HTMX. The URL for the API is configured via the `AUTH_API_URL` environment variable.

## API Endpoints

- `/api/events/suggest-form` - Returns the HTML form for suggesting events
- `/api/events/submit` - Handles form submission for new events

## Deployment

The service is included in the GitHub Actions workflow and will be built and pushed to ECR when code is merged to the main branch. The ECR repository is created by the CloudFormation template in `ecr-infrastructure.yaml`.

For production deployment, the container is built with the `LAMBDA_BUILD=true` build argument to create a Lambda-compatible image.

### Required GitHub Secrets

Add this secret to your GitHub repository:
- `ECR_REPOSITORY_AUTH_VIEWS`: The name of the ECR repository for authenticated user views (e.g., "cal-containers-auth-views")

## Authentication

This is currently a simple implementation without actual authentication. To implement authentication:

1. Add authentication middleware to the Flask app
2. Configure authentication providers (e.g., Cognito, Auth0)
3. Implement protected routes that require authentication