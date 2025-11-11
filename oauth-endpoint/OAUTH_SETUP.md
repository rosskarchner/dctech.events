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

### Part 2: OAuth Endpoint Implementation

The OAuth callback endpoint is implemented in the `oauth-endpoint/` directory of the dctech.events repository. The implementation in `oauth-endpoint/app.py` includes:

- OAuth callback route at `/oauth/callback`
- Secure retrieval of GitHub client secret from AWS Secrets Manager
- State parameter validation for CSRF protection
- Error handling and redirect logic

The complete implementation is in `oauth-endpoint/app.py` in this repository.

### Part 3: Deploy OAuth Client Secret to AWS Secrets Manager

The OAuth client secret is securely stored in AWS Secrets Manager and retrieved at runtime. To deploy the secret:

```bash
cd oauth-endpoint
python deploy_secrets.py "your_github_client_secret_here"
```

This will create a secret at `dctech-events/github-oauth-secret` in AWS Secrets Manager.

The Lambda function is automatically configured with IAM permissions to access this secret. See `oauth-endpoint/.chalice/policy-prod.json` for the IAM policy.

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

1. Deploy the OAuth endpoint (from the root of the dctech.events repository):
   ```bash
   cd oauth-endpoint
   chalice deploy --stage PROD
   ```

   Or, push your changes to the main branch and let GitHub Actions deploy automatically.

2. The dctech.events site is automatically rebuilt and deployed to GitHub Pages when changes are pushed to the main branch.

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
- Ensure the OAuth callback route is deployed (check `oauth-endpoint/` directory)
- Check API Gateway routes in AWS Console
- Verify the Chalice deployment completed successfully

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
