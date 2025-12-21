# AWS Location Services CloudFormation Setup

This directory contains CloudFormation templates for setting up AWS resources needed by DC Tech Events.

## Location Services IAM Template

The `location-services-iam.yaml` template creates:

1. **IAM User**: `dctech-events-location-services` - A dedicated user for the application
2. **IAM Policy**: Grants minimum required permissions for AWS Location Services geocoding
3. **Access Keys**: Credentials for the user to authenticate API calls

### Permissions Granted

The policy allows the following AWS Location Service actions:
- `geo:SearchPlaceIndexForText` - Search for places by text (address normalization)
- `geo:SearchPlaceIndexForPosition` - Search for places by coordinates
- `geo:GetPlace` - Get detailed information about a place

These permissions apply to all place indexes in the account.

### Deployment

1. **Deploy the Stack**:
   ```bash
   aws cloudformation create-stack \
     --stack-name dctech-events-location-services \
     --template-body file://location-services-iam.yaml \
     --capabilities CAPABILITY_NAMED_IAM
   ```

2. **Retrieve Credentials**:
   ```bash
   aws cloudformation describe-stacks \
     --stack-name dctech-events-location-services \
     --query 'Stacks[0].Outputs'
   ```

   **IMPORTANT**: Store the `SecretAccessKey` securely immediately after deployment. It cannot be retrieved later.

3. **Configure GitHub Secrets**:
   Add the following secrets to your GitHub repository:
   - `AWS_ACCESS_KEY_ID` - The Access Key ID from the stack outputs
   - `AWS_SECRET_ACCESS_KEY` - The Secret Access Key from the stack outputs
   - `AWS_REGION` - The AWS region for Location Services (e.g., `us-east-1`)
   - `AWS_LOCATION_INDEX_NAME` - The name of your AWS Location Service Place Index

4. **Create a Place Index** (if you haven't already):
   ```bash
   aws location create-place-index \
     --index-name dctech-events-places \
     --data-source Esri \
     --pricing-plan RequestBasedUsage
   ```

### Updating the Stack

```bash
aws cloudformation update-stack \
  --stack-name dctech-events-location-services \
  --template-body file://location-services-iam.yaml \
  --capabilities CAPABILITY_NAMED_IAM
```

### Deleting the Stack

```bash
aws cloudformation delete-stack \
  --stack-name dctech-events-location-services
```

**Note**: Delete the access keys from GitHub Secrets before deleting the stack.

## Security Best Practices

1. **Rotate Access Keys**: Regularly rotate the access keys for security
2. **Monitor Usage**: Set up CloudWatch alarms for unusual API usage
3. **Least Privilege**: The policy grants only the minimum permissions needed
4. **Secure Storage**: Never commit credentials to the repository
