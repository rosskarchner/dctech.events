# DC Tech Events Submission Form

This is a serverless web application built with AWS Chalice that allows users to submit events to the [DC Tech Events](https://github.com/rosskarchner/dctech.events) repository. The application provides a web form for event submission and handles the creation of pull requests through an email confirmation flow.

## Features

- Web form for event submission
- Email confirmation flow
- Automatic pull request creation
- Serverless architecture using AWS Lambda and API Gateway

## Prerequisites

- Python 3.8 or higher
- AWS Account and configured AWS CLI
- GitHub Personal Access Token with repo permissions
- Verified SES email address for sending emails

## Setup

1. Clone this repository
2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create the DynamoDB table:
   ```bash
   # Make the script executable
   chmod +x create_table.sh
   
   # Run the script to create the table
   ./create_table.sh
   ```

   The script will:
   - Check for AWS CLI installation
   - Verify AWS credentials are configured
   - Create the DynamoDB table with required schema
   - Wait for the table to be active

5. Update `.chalice/config.json`:
   - Set your AWS account ID
   - Configure the sender email address
   - Add your GitHub personal access token

6. Create an IAM role with the following permissions:
   - AWSLambdaBasicExecutionRole
   - DynamoDB access to the submissions table
   - SES send email permissions
   - Secrets Manager access for CSRF secret:
     ```json
     {
         "Version": "2012-10-17",
         "Statement": [
             {
                 "Effect": "Allow",
                 "Action": [
                     "secretsmanager:GetSecretValue"
                 ],
                 "Resource": [
                     "arn:aws:secretsmanager:*:*:secret:dctech-events/csrf-secret-*",
                     "arn:aws:secretsmanager:*:*:secret:dctech-events/github-token-*"
                 ]
             }
         ]
     }
     ```

## Deployment

Deploy the application using Chalice:

```bash
chalice deploy
```

The deployment will create:
- An API Gateway endpoint
- Lambda functions
- IAM roles and policies

## Local Development

Run the development server:

```bash
chalice local
```

The application will be available at http://localhost:8000

## Architecture

The application consists of several components:

1. **Frontend**: HTML form served by API Gateway/Lambda
2. **Backend API**: 
   - `/submit` endpoint for form submission
   - `/confirm/{submission_id}` endpoint for email confirmation
3. **AWS Services**:
   - DynamoDB for storing submissions
   - SES for sending emails
   - Lambda for serverless execution
4. **GitHub Integration**: Creates pull requests using the GitHub API

## Security Considerations

### CSRF Protection
The application uses CSRF tokens to protect forms from cross-site request forgery attacks. The CSRF secret key is stored in AWS Secrets Manager and should be:

- At least 32 characters long
- Randomly generated using a cryptographically secure random number generator
- Rotated every 90 days
- Unique per environment (development, staging, production)

To create a new CSRF secret:
```bash
# Generate a new secret
openssl rand -base64 32

# Store it in AWS Secrets Manager
aws secretsmanager create-secret \
    --name dctech-events/csrf-secret \
    --secret-string '{"CSRF_SECRET_KEY":"your-generated-key"}'
```

### Other Security Measures
- Use environment variables for non-secret configuration
- Implement rate limiting on the API Gateway
- Use AWS KMS for encrypting sensitive data
- Configure CORS appropriately
- Use secure HTTPS endpoints
- Regularly rotate all secrets and access keys

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License