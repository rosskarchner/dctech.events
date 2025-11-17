# Organize DC Tech Events Infrastructure

This CDK stack deploys a complete infrastructure for `organize.dctech.events`, a platform that allows community members to create and manage their own tech events and groups.

## Architecture Overview

The infrastructure consists of:

1. **CloudFront + S3**: Static website hosting for the React frontend
2. **Cognito User Pool**: User authentication and management
3. **API Gateway**: RESTful API with Cognito authorization
4. **Lambda Functions**:
   - API handler for all backend operations
   - Export function to generate YAML files
5. **DynamoDB Tables**:
   - Users (extended profile information)
   - Groups (tech groups/organizations)
   - Group Members (membership and roles)
   - Events (tech events)
   - RSVPs (event attendance tracking)
   - Messages (group communication)
6. **EventBridge Rule**: Scheduled exports every 5 minutes

## Features

### User Management
- Sign up with email verification
- Sign in with email/username
- Manage profile (bio, website)
- OAuth integration via Cognito

### Groups
- Create new groups
- Join/leave groups
- Three-tier role system:
  - **Owner**: Full control, can manage roles, delete group
  - **Manager**: Can create events, post messages, manage members
  - **Member**: Can view and post messages, RSVP to events
- Group messaging for members
- Active/inactive status

### Events
- Create standalone events or group events
- RSVP tracking (going/maybe/not going)
- Edit/delete events (creator or group managers)
- Convert event RSVPs to a new group
- Automatic export to main dctech.events calendar

### Integration with Main Site
- Groups and events are exported to YAML files every 5 minutes
- Main dctech.events site fetches these files during build
- Seamless integration with existing _groups and _single_events

## Prerequisites

- AWS CLI configured with appropriate credentials
- Node.js 18+ and npm (for CDK and Lambda only)
- AWS CDK CLI (\`npm install -g aws-cdk\`)
- An AWS account
- (Optional) A custom domain and ACM certificate

## Technology Stack

- **Frontend**: HTMX + Vanilla JavaScript (no build step required!)
- **Authentication**: Amazon Cognito Identity SDK
- **Styling**: Pure CSS
- **Backend**: API Gateway + Lambda (Node.js)
- **Database**: DynamoDB
- **Hosting**: CloudFront + S3

## Deployment

See DEPLOYMENT.md for detailed deployment instructions.

## API Documentation

See API.md for complete API endpoint documentation.

## Database Schema

See SCHEMA.md for complete database schema documentation.

## Cost Considerations

- **DynamoDB**: Pay-per-request pricing (cost-effective for low traffic)
- **Lambda**: Free tier covers 1M requests/month
- **API Gateway**: $3.50 per million requests
- **CloudFront**: $0.085 per GB + request charges
- **Cognito**: 50,000 MAU free, then $0.0055 per MAU
- **S3**: Minimal storage costs

Estimated monthly cost for moderate usage (1000 users, 100 events): **$10-30**

## Security

- All API endpoints use Cognito JWT authorization
- DynamoDB tables have fine-grained IAM permissions
- S3 bucket blocks public access (CloudFront OAI only)
- Point-in-time recovery enabled for data protection
- HTTPS enforced via CloudFront

## Contributing

To add new features:

1. Update CDK stack in \`lib/infrastructure-stack.ts\`
2. Add/modify Lambda functions in \`lambda/\`
3. Update frontend in \`frontend/src/\`
4. Deploy: \`npx cdk deploy\`
5. Build and upload frontend

## License

This infrastructure is part of the dctech.events project.
