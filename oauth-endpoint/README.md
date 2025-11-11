# DC Tech Events OAuth Endpoint

This is a serverless OAuth callback handler built with AWS Chalice that enables GitHub authentication for the [DC Tech Events](https://github.com/rosskarchner/dctech.events) event submission system.

**Note**: This code is part of the dctech.events repository in the `oauth-endpoint/` directory. It's deployed separately to AWS Lambda and provides the OAuth callback endpoint at `https://add.dctech.events/oauth/callback`.

## Features

- GitHub OAuth callback handler
- Secure exchange of authorization code for access token
- AWS Secrets Manager integration for client secret storage
- Serverless architecture using AWS Lambda and API Gateway

## Prerequisites

- Python 3.8 or higher
- AWS Account and configured AWS CLI
- GitHub OAuth App credentials (Client ID and Client Secret)

## Setup

1. Navigate to the oauth-endpoint directory:
   ```bash
   cd oauth-endpoint
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Deploy the GitHub OAuth client secret to AWS Secrets Manager:
   ```bash
   python deploy_secrets.py "your_github_client_secret_here"
   ```

   See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions.

## Deployment

### Manual Deployment

Deploy the application using Chalice:

```bash
chalice deploy --stage PROD
```

The deployment will create:
- An API Gateway endpoint
- Lambda function
- IAM roles and policies

### Automated Deployment

The application is automatically deployed via GitHub Actions when changes are pushed to the main branch that affect files in the `oauth-endpoint/` directory.

See [GITHUB_ACTIONS.md](GITHUB_ACTIONS.md) for complete documentation on:
- Required GitHub Secrets and their configuration
- IAM permissions needed for deployment
- Troubleshooting deployment issues
- Manual deployment instructions

Quick reference - Required GitHub Secrets:
- `AWS_ACCESS_KEY_ID` - AWS access key for deployment
- `AWS_SECRET_ACCESS_KEY` - AWS secret access key

**Required IAM Policy**: Apply the least-privilege policy from [`iam-deployment-policy.json`](iam-deployment-policy.json) to the IAM user associated with the AWS credentials.

**Note**: The GitHub OAuth client secret is stored in AWS Secrets Manager and is not managed via the GitHub Actions workflow.

## Local Development

Run the development server:

```bash
chalice local
```

The application will be available at http://localhost:8000

## Architecture

The OAuth endpoint is a single-purpose API that handles the GitHub OAuth callback:

1. **API Endpoint**: `/oauth/callback`
   - Receives authorization code from GitHub
   - Exchanges code for access token
   - Redirects back to dctech.events with token

2. **AWS Services**:
   - Lambda for serverless execution
   - API Gateway for HTTPS endpoint
   - Secrets Manager for storing GitHub client secret

3. **Security**:
   - Client secret stored in AWS Secrets Manager (never in code)
   - Client ID is public and hardcoded in app.py
   - State parameter validation for CSRF protection

## Security Considerations

1. **Client Secret**: Stored securely in AWS Secrets Manager at `dctech-events/github-oauth-secret`
   - Never committed to Git
   - Retrieved at runtime by Lambda
   - Managed via `deploy_secrets.py` script

2. **State Parameter**: CSRF protection via base64-encoded JSON state parameter
   - Contains random CSRF token
   - Specifies allowed return URL

3. **Access Token Handling**:
   - Token passed via URL parameter (temporary)
   - Immediately stored in sessionStorage by client
   - Never persisted to localStorage or cookies

4. **HTTPS Only**: All OAuth flows use secure HTTPS endpoints

5. **Rate Limiting**: Consider implementing rate limiting on API Gateway for production

For detailed security practices, see [DEPLOYMENT.md](DEPLOYMENT.md)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License