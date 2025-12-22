# AWS Places API v2 CloudFormation Setup

This directory contains CloudFormation templates for setting up AWS resources needed by DC Tech Events.

## Places API v2 IAM Template

The `location-services-iam.yaml` template creates:

1. **IAM User**: `dctech-events-places-api` - A dedicated user for the application
2. **IAM Policy**: Grants minimum required permissions for AWS Places API v2
3. **Access Keys**: Credentials for the user to authenticate API calls

### Permissions Granted

The policy allows the following AWS Places API v2 actions:
- `geo-places:SearchText` - Search for places by text (address normalization)
- `geo-places:Geocode` - Convert addresses to coordinates
- `geo-places:ReverseGeocode` - Convert coordinates to addresses
- `geo-places:GetPlace` - Get detailed information about a place

These permissions apply to all resources (using wildcard `*`) as the new Places API v2 does not require managing place index resources.

### Deployment

1. **Deploy the Stack**:
   ```bash
   aws cloudformation create-stack \
     --stack-name dctech-events-places-api \
     --template-body file://location-services-iam.yaml \
     --capabilities CAPABILITY_NAMED_IAM
   ```

2. **Retrieve Credentials**:
   ```bash
   aws cloudformation describe-stacks \
     --stack-name dctech-events-places-api \
     --query 'Stacks[0].Outputs'
   ```

   **IMPORTANT**: Store the `SecretAccessKey` securely immediately after deployment. It cannot be retrieved later.

3. **Configure GitHub Secrets**:
   Add the following secrets to your GitHub repository:
   - `AWS_ACCESS_KEY_ID` - The Access Key ID from the stack outputs
   - `AWS_SECRET_ACCESS_KEY` - The Secret Access Key from the stack outputs
   - `AWS_REGION` - The AWS region for Places API (e.g., `us-east-1`)

   **Note**: `AWS_LOCATION_INDEX_NAME` is no longer needed with Places API v2.

### Updating the Stack

```bash
aws cloudformation update-stack \
  --stack-name dctech-events-places-api \
  --template-body file://location-services-iam.yaml \
  --capabilities CAPABILITY_NAMED_IAM
```

### Deleting the Stack

```bash
aws cloudformation delete-stack \
  --stack-name dctech-events-places-api
```

**Note**: Delete the access keys from GitHub Secrets before deleting the stack.

## Migration from Location Services v1

If you're migrating from the old Location Services (place index) setup:

1. **No Place Index Required**: The new Places API v2 doesn't require creating or managing a place index
2. **Updated Permissions**: The IAM policy now uses `geo-places:*` actions instead of `geo:*`
3. **Simplified Configuration**: Remove `AWS_LOCATION_INDEX_NAME` from your environment variables
4. **Boto3 Requirement**: Ensure boto3 >= 1.40.0 is installed

## Security Best Practices

1. **Rotate Access Keys**: Regularly rotate the access keys for security
2. **Monitor Usage**: Set up CloudWatch alarms for unusual API usage
3. **Least Privilege**: The policy grants only the minimum permissions needed
4. **Secure Storage**: Never commit credentials to the repository
