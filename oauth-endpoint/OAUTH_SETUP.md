# GitHub OAuth Setup for Event Submission

This document describes how to enable GitHub OAuth authentication for the event submission page.

## Overview

The event submission feature allows users to submit events directly through the dctech.events website by:
1. Signing in with their GitHub account
2. Filling out an event form
3. Automatically creating a Pull Request to the repository with their event data

The implementation uses **client-side JavaScript** (Octokit.js) for all GitHub API interactions, making it compatible with static site hosting. However, GitHub OAuth requires a server-side component to securely exchange the authorization code for an access token.

## Architecture

```
┌─────────────┐      1. Click Login       ┌──────────────────┐
│  User       │ ───────────────────────> │  dctech.events   │
│  Browser    │                           │  /submit/        │
└─────────────┘                           └──────────────────┘
      │                                            │
      │ 2. Redirect to GitHub OAuth               │
      ▼                                            │
┌─────────────┐                                   │
│  GitHub     │                                   │
│  OAuth      │ <─────────────────────────────────┘
└─────────────┘
      │ 3. User authorizes
      │
      ▼
┌─────────────────────────┐
│  add.dctech.events      │
│  /oauth/callback        │  4. Exchange code for token
│  (Server-side)          │
└─────────────────────────┘
      │
      │ 5. Redirect with token
      ▼
┌─────────────┐
│  dctech.events          │
│  /submit/?access_token= │  6. Client-side PR creation
└─────────────────────────┘
```

## Setup Instructions

### Part 1: Create GitHub OAuth App

1. Go to GitHub Settings > Developer Settings > OAuth Apps
2. Click "New OAuth App"
3. Fill in the details:
   - **Application name**: `dctech.events Event Submission`
   - **Homepage URL**: `https://dctech.events`
   - **Authorization callback URL**: `https://add.dctech.events/oauth/callback`
   - **Application description**: "Submit tech events to dctech.events"

4. Save the **Client ID** and **Client Secret**

### Part 2: Extend add.dctech.events

The existing `add.dctech.events` repository needs a new OAuth callback endpoint. Add the following to `app.py`:

```python
import os
import requests
from chalice import Response

# Add this route to app.py
@app.route('/oauth/callback', methods=['GET'])
def oauth_callback():
    """
    Handle GitHub OAuth callback
    Exchange authorization code for access token
    """
    # Get authorization code from query params
    code = app.current_request.query_params.get('code')
    state = app.current_request.query_params.get('state')
    error = app.current_request.query_params.get('error')

    # Handle errors
    if error:
        return Response(
            body='',
            status_code=302,
            headers={
                'Location': f'https://dctech.events/submit/?error={error}'
            }
        )

    if not code:
        return Response(
            body='',
            status_code=302,
            headers={
                'Location': 'https://dctech.events/submit/?error=missing_code'
            }
        )

    # Get OAuth credentials from environment
    client_id = os.environ.get('GITHUB_CLIENT_ID')
    client_secret = os.environ.get('GITHUB_CLIENT_SECRET')

    if not client_id or not client_secret:
        return Response(
            body='',
            status_code=302,
            headers={
                'Location': 'https://dctech.events/submit/?error=oauth_not_configured'
            }
        )

    # Exchange code for access token
    try:
        token_response = requests.post(
            'https://github.com/login/oauth/access_token',
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            json={
                'client_id': client_id,
                'client_secret': client_secret,
                'code': code,
                'state': state
            }
        )

        token_data = token_response.json()

        if 'error' in token_data:
            return Response(
                body='',
                status_code=302,
                headers={
                    'Location': f'https://dctech.events/submit/?error={token_data["error"]}'
                }
            )

        access_token = token_data.get('access_token')

        if not access_token:
            return Response(
                body='',
                status_code=302,
                headers={
                    'Location': 'https://dctech.events/submit/?error=no_token'
                }
            )

        # Redirect back to dctech.events with the access token
        return Response(
            body='',
            status_code=302,
            headers={
                'Location': f'https://dctech.events/submit/?access_token={access_token}'
            }
        )

    except Exception as e:
        print(f"OAuth error: {str(e)}")
        return Response(
            body='',
            status_code=302,
            headers={
                'Location': 'https://dctech.events/submit/?error=exchange_failed'
            }
        )
```

### Part 3: Update add.dctech.events Configuration

Update `.chalice/config.json` to include the OAuth credentials:

```json
{
  "version": "2.0",
  "app_name": "add-dctech-events",
  "stages": {
    "dev": {
      "api_gateway_stage": "api",
      "environment_variables": {
        "GITHUB_CLIENT_ID": "your_client_id_here",
        "GITHUB_CLIENT_SECRET": "your_client_secret_here",
        "GITHUB_TOKEN": "existing_token_for_pr_creation",
        "SENDER_EMAIL": "existing_email",
        "SITE_SLUG": "dctech"
      }
    }
  }
}
```

**Security Best Practice**: Instead of storing the client secret in config.json, use AWS Secrets Manager:

```python
import boto3
import json

def get_oauth_credentials():
    """Get OAuth credentials from AWS Secrets Manager"""
    secrets_client = boto3.client('secretsmanager')

    try:
        secret = secrets_client.get_secret_value(SecretId='github-oauth-credentials')
        credentials = json.loads(secret['SecretString'])
        return credentials.get('client_id'), credentials.get('client_secret')
    except Exception as e:
        print(f"Error retrieving secrets: {str(e)}")
        return None, None
```

Then update the IAM policy to allow access to Secrets Manager:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:region:account-id:secret:github-oauth-credentials-*"
    }
  ]
}
```

### Part 4: Configure dctech.events

Update `config.yaml` to include the OAuth settings:

```yaml
site_name: DC Tech Events
tagline: Technology events in the DC area
timezone: US/Eastern
base_url: https://dctech.events
add_events_link: https://add.dctech.events
newsletter_signup_link: https://newsletter.dctech.events

# GitHub OAuth Configuration
github_client_id: your_client_id_here
oauth_callback_endpoint: https://add.dctech.events/oauth/callback
```

Alternatively, use environment variables (recommended for production):

```bash
export GITHUB_CLIENT_ID=your_client_id_here
export OAUTH_CALLBACK_ENDPOINT=https://add.dctech.events/oauth/callback
```

### Part 5: Deploy

1. Deploy the updated add.dctech.events:
   ```bash
   cd add.dctech.events
   chalice deploy
   ```

2. Rebuild and deploy dctech.events:
   ```bash
   cd dctech.events
   make clean
   make
   python freeze.py
   # Deploy the build/ directory to GitHub Pages
   ```

## Testing

1. Navigate to `https://dctech.events/submit/`
2. Click "Sign in with GitHub"
3. Authorize the application
4. Fill out the event form
5. Submit to create a Pull Request

## Security Considerations

1. **Client Secret**: Never expose the GitHub client secret in client-side code. It must only exist in the server-side OAuth callback handler.

2. **Access Token**: The access token is temporarily passed via URL parameter and stored in sessionStorage. It's never persisted to localStorage or cookies. Consider encrypting the token parameter for added security.

3. **CORS**: The add.dctech.events endpoint should set appropriate CORS headers if needed:
   ```python
   'Access-Control-Allow-Origin': 'https://dctech.events'
   ```

4. **State Parameter**: The OAuth flow includes a state parameter to prevent CSRF attacks. The client generates a random state and verifies it on return.

5. **Rate Limiting**: Consider adding rate limiting to the OAuth callback endpoint to prevent abuse.

## Troubleshooting

### "GitHub OAuth is not configured"
- Check that `github_client_id` is set in config.yaml or environment variables
- Verify the OAuth callback endpoint URL is correct

### "Authentication failed"
- Check the GitHub OAuth App settings
- Verify the callback URL matches exactly
- Check the add.dctech.events deployment logs

### "Failed to create pull request"
- Ensure the user has forked the repository
- Check GitHub API rate limits
- Verify the access token has the correct scopes (public_repo)

### "No matching routes found"
- Ensure the OAuth callback route is deployed in add.dctech.events
- Check API Gateway routes in AWS Console

## Alternative: GitHub Device Flow

If you prefer to avoid server-side OAuth, you can use GitHub's Device Flow:

```javascript
// Device Flow example
async function authenticateWithDeviceFlow() {
    const response = await fetch('https://github.com/login/device/code', {
        method: 'POST',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            client_id: CONFIG.clientId,
            scope: 'public_repo'
        })
    });

    const data = await response.json();

    // Show user_code and verification_uri to the user
    alert(`Go to ${data.verification_uri} and enter code: ${data.user_code}`);

    // Poll for authentication
    // ... implementation details
}
```

The Device Flow doesn't require a client secret, but the UX is less smooth (user must copy a code to GitHub).

## Future Enhancements

1. **Fork Management**: Automatically fork the repository if the user hasn't already
2. **Validation**: Add client-side YAML validation before creating PR
3. **Preview**: Show a preview of the event before submission
4. **Draft PRs**: Create draft PRs that users can finalize later
5. **Multiple Events**: Allow submitting multiple events in one PR
6. **Image Upload**: Support uploading event images to the PR

## Support

For issues or questions:
- File an issue: https://github.com/rosskarchner/dctech.events/issues
- Email: ross@karchner.com
