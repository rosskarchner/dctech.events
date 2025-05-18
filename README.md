# DC Tech Events

A platform for aggregating and displaying tech events in the DC area.

## Local Development

To run the application locally:

```bash
docker-compose up
```

This will start the following services:
- Frontend app at http://localhost:5000
- DynamoDB local at http://localhost:8000
- S3 emulator (LocalStack) at http://localhost:4566
- Aggregator Lambda function

## Deployment

### Prerequisites

1. AWS CLI installed and configured
2. SAM CLI installed
3. Docker installed

### Deployment with SAM

The application is now configured to build and deploy as a single unit using AWS SAM:

```bash
# Make the deployment script executable
chmod +x deploy.sh

# Deploy with default settings
./deploy.sh

# Deploy with custom settings
./deploy.sh \
  --stack-name dctech-events-dev \
  --environment dev \
  --domain-name dev.dctech.events \
  --auth-domain auth.dev.dctech.events \
  --region us-east-1

# Build without deploying
./deploy.sh --build-only

# Delete the stack
./deploy.sh --delete
```

The deployment script will:
1. Build the container images for the Lambda functions using SAM
2. Deploy the entire stack as one unit
3. Display the outputs from the CloudFormation stack

### Manual Deployment

If you prefer to deploy manually:

```bash
# Build the application
sam build --template template.yaml

# Deploy the application
sam deploy \
  --stack-name dctech-events \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    DomainName=dctech.events \
    AuthDomainName=auth.dctech.events \
    Environment=prod
```

## Architecture

The deployed infrastructure includes:

- **CloudFront Distribution**: Serves the static site and routes API requests
- **S3 Bucket**: Stores the static site files
- **DynamoDB Tables**: Store events and groups data
- **Cognito User Pool**: Handles authentication
- **Lambda Functions**:
  - Aggregator: Runs hourly to fetch and process events
  - Static Site Generator: Runs hourly to generate and upload the static site
  - API: Handles authenticated API requests

## API Routes

All API routes are protected by Cognito authentication and are available under the `/api/` path:

- `/api/events/suggest-form`: Get the event suggestion form
- `/api/events/submit`: Submit a new event
- `/api/events/review`: Review pending events
- `/api/events/approve/{id}`: Approve an event
- `/api/events/delete/{id}`: Delete an event
- `/api/groups/manage`: Manage groups
- `/api/groups/approve/{id}`: Approve a group
- `/api/groups/delete/{id}`: Delete a group

## Authentication

Authentication is handled by Amazon Cognito. Users can sign in at `https://auth.dctech.events`.

## Additional Documentation

- [Authenticated Views](README-authenticated-views.md)
- [Deployment Details](README-deployment.md)
- [Recent Changes](README-changes.md)