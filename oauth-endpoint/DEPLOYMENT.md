# Deployment Guide: GitHub OAuth with AWS Secrets Manager

This guide explains how to deploy the application with GitHub OAuth credentials managed by AWS Secrets Manager.

## Architecture

- **Client ID**: Hardcoded in `app.py` (public information, safe to commit)
  - Value: `Ov23liSTVbSKSvkYW6yg`
- **Client Secret**: Stored securely in AWS Secrets Manager
  - Secret ID: `dctech-events/github-oauth-secret`
  - Automatically retrieved at runtime by the Lambda function

## Prerequisites

1. AWS Account with appropriate permissions:
   - `secretsmanager:CreateSecret`
   - `secretsmanager:UpdateSecret`
   - `secretsmanager:GetSecretValue` (already granted to Lambda via IAM policy)

2. AWS CLI configured with credentials:
   ```bash
   aws configure
   ```

3. GitHub OAuth credentials:
   - Client ID: `Ov23liSTVbSKSvkYW6yg` (already hardcoded)
   - Client Secret: Your GitHub app's client secret (from https://github.com/settings/developers)

## Deployment Steps

### Step 1: Deploy the GitHub Secret to AWS Secrets Manager

Run the deployment script before deploying the Chalice application:

```bash
python deploy_secrets.py "your_github_client_secret_here"
```

Or use an environment variable:

```bash
export GITHUB_CLIENT_SECRET="your_github_client_secret_here"
python deploy_secrets.py
```

**Options:**
- `--region us-west-2`: Deploy to a specific AWS region (default: us-east-1)
- `--create-only`: Only create the secret, don't update if it already exists

**Example:**
```bash
python deploy_secrets.py "ghu_16C7e42F292c6912E7710c838347Ae178B4a" --region us-east-1
```

**Success output:**
```
Deploying GitHub OAuth secret to AWS Secrets Manager (us-east-1)...
Successfully created secret dctech-events/github-oauth-secret
Secret ARN: arn:aws:secretsmanager:us-east-1:797438674243:secret:dctech-events/github-oauth-secret-abcde

✓ Secret deployment successful!
The application will use this secret at: dctech-events/github-oauth-secret
```

### Step 2: Deploy the Chalice Application

After successfully deploying the secret:

```bash
chalice deploy
```

This will:
1. Package the Python application
2. Create/update the Lambda function
3. Configure API Gateway routes
4. Apply the IAM policy that includes Secrets Manager access

## Verification

### Verify the Secret is Stored

```bash
# View secret metadata
aws secretsmanager describe-secret --secret-id dctech-events/github-oauth-secret

# View secret value (if needed for debugging)
aws secretsmanager get-secret-value --secret-id dctech-events/github-oauth-secret
```

### Test the OAuth Flow

1. Visit: `https://dctech.events/submit`
2. Click "Connect with GitHub"
3. Authorize the application
4. Confirm you're redirected with an access token

### Check Lambda Logs

```bash
# View recent logs
chalice logs

# Or via CloudWatch
aws logs tail /aws/lambda/dctech-events-submit-dev --follow
```

## Troubleshooting

### "error=oauth_not_configured"

This indicates the client secret was not retrieved from Secrets Manager. Check:

1. **Secret exists in Secrets Manager:**
   ```bash
   aws secretsmanager get-secret-value --secret-id dctech-events/github-oauth-secret
   ```

2. **Lambda has IAM permissions:**
   - Check `.chalice/policy.json` includes:
     ```json
     {
       "Effect": "Allow",
       "Action": ["secretsmanager:GetSecretValue"],
       "Resource": ["arn:aws:secretsmanager:*:*:secret:dctech-events/*"]
     }
     ```

3. **Lambda logs for detailed error:**
   ```bash
   chalice logs
   ```

### "AccessDenied" or "User is not authorized to perform: secretsmanager:GetSecretValue"

The Lambda execution role doesn't have permission to access Secrets Manager. This is already configured in `.chalice/policy.json`. If you see this error:

1. Verify the policy was applied:
   ```bash
   aws iam get-role-policy \
     --role-name dctech-events-submit-dev-api_handler \
     --policy-name dctech-events-submit-dev
   ```

2. Redeploy Chalice to reapply the policy:
   ```bash
   chalice deploy
   ```

### Updating the Secret

To update the GitHub client secret (e.g., if it was regenerated):

```bash
python deploy_secrets.py "new_github_client_secret_here"
```

No redeployment of the Chalice app is needed—the Lambda will pick up the updated secret on the next request.

## Security Best Practices

1. **Never commit secrets to Git** - The deployment script is the only way to manage secrets
2. **Rotate secrets regularly** - Use the `deploy_secrets.py` script to update
3. **Audit secret access** - Monitor CloudTrail logs:
   ```bash
   aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=GetSecretValue
   ```
4. **Restrict secret access** - The current IAM policy limits to `dctech-events/*` secrets only
5. **Monitor failed OAuth attempts** - Check CloudWatch logs for OAuth errors

## Environment Variables (Deprecated)

The application previously read credentials from environment variables:
- `GITHUB_CLIENT_ID` - Replaced with hardcoded constant
- `GITHUB_CLIENT_SECRET` - Replaced with Secrets Manager retrieval

These are no longer used and should be removed from any CI/CD configuration or Lambda environment variables.

## CI/CD Integration

For automated deployments, update your CI/CD pipeline to:

1. **Deploy secret before application:**
   ```bash
   GITHUB_CLIENT_SECRET=${{ secrets.GITHUB_CLIENT_SECRET }} python deploy_secrets.py
   chalice deploy
   ```

2. **Use GitHub Secrets** to store the client secret (not in the code)

Example GitHub Actions workflow:
```yaml
- name: Deploy GitHub OAuth Secret
  env:
    GITHUB_CLIENT_SECRET: ${{ secrets.GITHUB_CLIENT_SECRET }}
  run: python deploy_secrets.py

- name: Deploy Chalice Application
  run: chalice deploy
```

## IAM Policy Reference

The Lambda function needs these permissions (already in `.chalice/policy.json`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": ["arn:aws:secretsmanager:*:*:secret:dctech-events/*"]
    }
  ]
}
```

This grants read-only access to any secret under `dctech-events/*`, which includes:
- `dctech-events/github-oauth-secret` (GitHub OAuth client secret)
- `dctech-events/csrf-secret` (CSRF token secret, if applicable)
- `dctech-events/github-token` (GitHub API token, if applicable)

## Additional Resources

- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [GitHub OAuth Documentation](https://docs.github.com/en/apps/oauth-apps)
- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [Chalice Documentation](https://aws.github.io/chalice/)
