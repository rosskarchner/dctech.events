# GitHub Actions Configuration for OAuth Endpoint Deployment

This document describes the GitHub Actions secrets and variables required for automated deployment of the OAuth endpoint.

## Overview

The OAuth endpoint is automatically deployed to AWS Lambda via GitHub Actions when changes are pushed to the `main` branch. The workflow is defined in `.github/workflows/deploy-oauth.yml`.

## Workflow Triggers

The deployment workflow runs when:
- Changes are pushed to the `main` branch that affect:
  - Files in the `oauth-endpoint/` directory
  - The workflow file itself (`.github/workflows/deploy-oauth.yml`)
- The workflow is manually triggered via `workflow_dispatch`

The workflow runs **in parallel** with the GitHub Pages deployment workflow, so both the main site and OAuth endpoint can be deployed simultaneously.

## Required GitHub Secrets

Configure these secrets in your repository settings at `Settings > Secrets and variables > Actions > Repository secrets`:

### 1. `AWS_ACCESS_KEY_ID`
- **Description**: AWS access key ID for deploying to AWS
- **Usage**: Used by the AWS CLI and Chalice to authenticate with AWS
- **How to obtain**:
  1. Log into AWS Console
  2. Go to IAM > Users > [your deployment user] > Security credentials
  3. Create an access key if one doesn't exist
  4. Copy the Access Key ID

### 2. `AWS_SECRET_ACCESS_KEY`
- **Description**: AWS secret access key for deploying to AWS
- **Usage**: Used by the AWS CLI and Chalice to authenticate with AWS
- **How to obtain**:
  1. Created at the same time as the Access Key ID
  2. Copy the Secret Access Key (you can only see this once!)
  3. Store it securely - if lost, you'll need to create a new access key

## GitHub OAuth Client Secret (Managed Separately)

The GitHub OAuth client secret is **NOT** deployed via this workflow. It is stored in AWS Secrets Manager at `dctech-events/github-oauth-secret` and should be managed manually.

To update the secret manually:
```bash
cd oauth-endpoint
python deploy_secrets.py "your_github_client_secret_here"
```

Or use the AWS CLI:
```bash
aws secretsmanager update-secret \
  --secret-id dctech-events/github-oauth-secret \
  --secret-string "your_github_client_secret_here"
```

## Required IAM Permissions

The AWS user/role associated with `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` needs the following permissions.

### Quick Setup: Use the Consolidated Policy

A complete least-privilege IAM policy is available in [`iam-deployment-policy.json`](iam-deployment-policy.json).

**To apply this policy:**

1. Go to AWS Console > IAM > Users > [your deployment user]
2. Click "Add permissions" > "Create inline policy"
3. Click the "JSON" tab
4. Copy and paste the contents of `iam-deployment-policy.json`
5. Review and create the policy

**Or via AWS CLI:**
```bash
aws iam put-user-policy \
  --user-name your-deployment-user \
  --policy-name DCtechEventsOAuthDeployment \
  --policy-document file://oauth-endpoint/iam-deployment-policy.json
```

### What's Included

The policy grants the minimum permissions needed for Chalice deployment:

- **Lambda**: Create, update, and manage `dctech-events-submit-*` functions
- **API Gateway**: Create and manage REST APIs for the OAuth endpoint
- **IAM**: Create and manage the Lambda execution role (`dctech-events-submit-*`)
- **Secrets Manager**: Read access to `dctech-events/*` secrets (for the OAuth client secret)
- **CloudFormation**: Manage stacks created by Chalice (`dctech-events-submit-*`)
- **CloudWatch Logs**: Read logs for debugging and verification

All permissions are scoped to resources with the `dctech-events-submit-` prefix where possible.

## Workflow Steps

The deployment workflow performs the following steps:

1. **Checkout code**: Checks out the repository
2. **Set up Python**: Installs Python 3.10
3. **Cache dependencies**: Caches pip dependencies for faster builds
4. **Install dependencies**: Installs requirements and AWS CLI
5. **Configure AWS credentials**: Sets up AWS authentication using secrets
6. **Deploy Chalice app**: Runs `chalice deploy --stage PROD` to deploy the Lambda function and API Gateway
7. **Get deployment info**: Outputs the API Gateway endpoint URL

## Deployment Output

After successful deployment, the workflow will output the API Gateway endpoint URL. The endpoint should be configured as:
- **URL**: `https://[api-id].execute-api.us-east-1.amazonaws.com/api/oauth/callback`
- **Custom domain**: Point `add.dctech.events` to this endpoint (manual configuration required)

## Verifying Deployment

To verify the deployment was successful:

1. Check the GitHub Actions workflow run in the `Actions` tab
2. Log into AWS Console > Lambda > Functions
3. Look for the function: `dctech-events-submit-PROD`
4. Check CloudWatch Logs for any errors
5. Test the OAuth flow: Visit `https://dctech.events/submit/` and click "Sign in with GitHub"

## Troubleshooting

### "AccessDenied" errors during deployment
- Check that the AWS IAM user has all required permissions listed above
- Verify the AWS credentials in GitHub Secrets are correct and not expired

### Deployment succeeds but OAuth doesn't work
- Check that the GitHub OAuth client secret was deployed correctly:
  ```bash
  aws secretsmanager get-secret-value --secret-id dctech-events/github-oauth-secret
  ```
- Verify the Lambda function has permission to read from Secrets Manager
- Check CloudWatch Logs for detailed error messages

### API Gateway endpoint changed
- If the API Gateway endpoint URL changes after deployment, you'll need to:
  1. Update your custom domain mapping (if using one)
  2. Update the `oauth_callback_endpoint` in `config.yaml` if not using a custom domain

## Manual Deployment

If you need to deploy manually (outside of GitHub Actions):

```bash
# 1. Configure AWS credentials
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1

# 2. Navigate to oauth-endpoint directory
cd oauth-endpoint

# 3. Deploy the Chalice app
chalice deploy --stage PROD
```

**Note**: The GitHub OAuth secret is managed separately. If you need to update it:

```bash
# Only needed when initially setting up or rotating the secret
export GITHUB_CLIENT_SECRET=your_github_oauth_client_secret
python deploy_secrets.py
```

## Security Best Practices

1. **Rotate credentials regularly**: Rotate AWS access keys and GitHub OAuth secrets every 90 days
2. **Use least privilege**: Only grant the IAM permissions listed above, nothing more
3. **Monitor CloudWatch Logs**: Set up alerts for failed OAuth attempts
4. **Enable CloudTrail**: Monitor API calls to AWS services for security auditing
5. **Use AWS Organizations**: Consider using AWS Organizations to isolate this deployment in its own account

## Support

For issues with the GitHub Actions workflow:
- Check the workflow run logs in the `Actions` tab
- File an issue: https://github.com/rosskarchner/dctech.events/issues
- Email: ross@karchner.com
