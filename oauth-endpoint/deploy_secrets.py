#!/usr/bin/env python3
"""
Deploy GitHub OAuth secret to AWS Secrets Manager.

Usage:
    python deploy_secrets.py <github_client_secret> [--region us-east-1] [--create-only]

Environment variables:
    GITHUB_CLIENT_SECRET: GitHub OAuth client secret (alternative to command line argument)
    AWS_REGION: AWS region (default: us-east-1)

Example:
    python deploy_secrets.py "your_github_secret_here"
    GITHUB_CLIENT_SECRET="your_github_secret_here" python deploy_secrets.py
"""

import sys
import argparse
import json
import os
import boto3
from botocore.exceptions import ClientError

def create_or_update_secret(client_secret, region='us-east-1', create_only=False):
    """
    Create or update the GitHub OAuth secret in AWS Secrets Manager.

    Args:
        client_secret: The GitHub OAuth client secret
        region: AWS region (default: us-east-1)
        create_only: If True, only create the secret (don't update if it exists)

    Returns:
        Tuple of (success: bool, message: str, arn: str)
    """
    client = boto3.client('secretsmanager', region_name=region)
    secret_id = 'dctech-events/github-oauth-secret'

    secret_value = json.dumps({
        'client_secret': client_secret
    })

    try:
        # Try to get the secret first
        client.describe_secret(SecretId=secret_id)

        if create_only:
            return False, f"Secret {secret_id} already exists (skipping due to --create-only flag)", None

        # Secret exists, update it
        response = client.update_secret(
            SecretId=secret_id,
            SecretString=secret_value
        )
        return True, f"Successfully updated secret {secret_id}", response.get('ARN')

    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            # Secret doesn't exist, create it
            try:
                response = client.create_secret(
                    Name=secret_id,
                    Description='GitHub OAuth client secret for dctech.events',
                    SecretString=secret_value,
                    Tags=[
                        {
                            'Key': 'Application',
                            'Value': 'dctech-events-submit'
                        },
                        {
                            'Key': 'Environment',
                            'Value': 'dev'
                        }
                    ]
                )
                return True, f"Successfully created secret {secret_id}", response.get('ARN')
            except ClientError as create_error:
                return False, f"Failed to create secret: {create_error.response['Error']['Message']}", None
        else:
            return False, f"Error accessing secret: {e.response['Error']['Message']}", None
    except Exception as e:
        return False, f"Unexpected error: {str(e)}", None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Deploy GitHub OAuth secret to AWS Secrets Manager'
    )
    parser.add_argument(
        'client_secret',
        nargs='?',
        help='GitHub OAuth client secret'
    )
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region (default: us-east-1)'
    )
    parser.add_argument(
        '--create-only',
        action='store_true',
        help='Only create the secret, do not update if it exists'
    )

    args = parser.parse_args()

    # Get the client secret
    client_secret = args.client_secret or os.environ.get('GITHUB_CLIENT_SECRET')

    if not client_secret:
        print("Error: GitHub OAuth client secret not provided", file=sys.stderr)
        print("Provide it as a command-line argument or GITHUB_CLIENT_SECRET environment variable", file=sys.stderr)
        parser.print_help()
        return 1

    # Validate secret is not empty
    if not client_secret.strip():
        print("Error: GitHub OAuth client secret is empty", file=sys.stderr)
        return 1

    print(f"Deploying GitHub OAuth secret to AWS Secrets Manager ({args.region})...")

    success, message, arn = create_or_update_secret(
        client_secret,
        region=args.region,
        create_only=args.create_only
    )

    print(message)
    if arn:
        print(f"Secret ARN: {arn}")

    if success:
        print("\n✓ Secret deployment successful!")
        print(f"The application will use this secret at: dctech-events/github-oauth-secret")
        return 0
    else:
        print("\n✗ Secret deployment failed!", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
