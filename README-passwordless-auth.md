# Passwordless Email-Only Authentication

This document describes the implementation of passwordless email-only authentication with automatic account creation for new users.

## Overview

The authentication system has been configured to allow users to sign in using only their email address. When a user attempts to sign in:

1. If the email is already associated with an account, a verification code is sent to that email
2. If the email is not associated with any account, a new account is automatically created and a verification code is sent to that email
3. The user enters the verification code to complete the authentication process

## Implementation Details

### AWS Cognito User Pool Configuration

The Cognito User Pool has been configured with the following settings:

- `UsernameAttributes` set to `email` to use email as the primary identifier
- `AutoVerifiedAttributes` set to `email` to automatically verify email addresses
- `AdminCreateUserConfig.AllowAdminCreateUserOnly` set to `false` to allow users to sign up themselves
- `UsernameConfiguration.CaseSensitive` set to `false` to make usernames case-insensitive
- Password policy simplified to support passwordless flow
- Lambda triggers configured for custom authentication flow

### Lambda Triggers

Four Lambda functions have been implemented to handle the passwordless authentication flow:

1. **PreSignUp**: Automatically confirms and verifies new users
2. **DefineAuthChallenge**: Manages the authentication challenge flow, including handling new user creation
3. **CreateAuthChallenge**: Generates and sends a verification code to the user's email
4. **VerifyAuthChallengeResponse**: Verifies the code entered by the user

### Client-Side Implementation

The client-side implementation includes:

- Updated `auth_callback.html` template to handle the passwordless authentication flow
- Added UI for entering the verification code
- JavaScript functions to verify the code and complete the authentication process

## Testing

A new test has been added to verify the passwordless authentication implementation:

- `test_passwordless_auth()` in `test_components.py`
- `test_passwordless_auth.py` for more detailed testing

## Usage

Users can authenticate by:

1. Navigating to the login page
2. Entering their email address
3. Receiving a verification code via email
4. Entering the verification code to complete the authentication process

If the email is not associated with an existing account, a new account will be automatically created.

## Security Considerations

- Email verification is required to ensure that users own the email addresses they use
- Verification codes are randomly generated 6-digit numbers
- Codes expire after a short period for security
- The system uses AWS Cognito's built-in security features for authentication

## Future Improvements

Potential future improvements include:

- Adding support for multi-factor authentication as an optional security feature
- Implementing account linking for users who want to connect multiple email addresses
- Adding social identity provider integration (Google, Facebook, etc.)