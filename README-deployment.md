# Deployment Guide for DC Tech Events

This guide explains how to deploy the DC Tech Events application using AWS SAM.

## Prerequisites

Before deploying, ensure you have:

1. AWS CLI installed and configured with appropriate permissions
2. AWS SAM CLI installed
3. Docker installed and running
4. A domain name (optional, but recommended for production)

## Deployment Options

### Option 1: Using the Deployment Script (Recommended)

We provide a deployment script that simplifies the process:

```bash
# Make the script executable
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

# Show all available options
./deploy.sh --help
```

### Option 2: Manual Deployment

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

## How It Works

The deployment process:

1. **Build Phase**: SAM builds Docker container images for each Lambda function using the Dockerfiles in the respective directories.
2. **Deploy Phase**: SAM deploys the CloudFormation stack, which includes:
   - Lambda functions with the built container images
   - DynamoDB tables
   - S3 bucket for static site
   - Cognito User Pool
   - API Gateway
   - CloudFront distribution

## Post-Deployment Steps

After deployment, you'll need to:

1. **Configure DNS**: Point your domain to the CloudFront distribution URL (found in the stack outputs)
2. **Validate SSL Certificate**: Follow the instructions in the AWS Certificate Manager console
3. **Create Users**: Set up users in the Cognito User Pool
4. **Load Sample Data**: Use the provided scripts to load sample data if needed

## Environment Variables

The following environment variables are set for the Lambda functions:

- `EVENTS_TABLE`: Name of the DynamoDB table for events
- `GROUPS_TABLE`: Name of the DynamoDB table for groups
- `S3_BUCKET_NAME`: Name of the S3 bucket for the static site
- `TIMEZONE`: Set to US/Eastern
- `SITEURL`: The URL of the site
- `SITENAME`: Set to "DC Tech Events"
- `ENVIRONMENT`: The deployment environment (dev or prod)

## Maintenance

- Monitor the Lambda functions in CloudWatch Logs
- Update the application code and redeploy as needed
- Back up the DynamoDB tables regularly

## Troubleshooting

If you encounter issues during deployment:

1. Check the CloudFormation events in the AWS Console
2. Review the SAM CLI output for errors
3. Check the Lambda function logs in CloudWatch
4. Ensure your AWS credentials have the necessary permissions

For more specific issues, refer to the AWS SAM documentation or open an issue in the project repository.