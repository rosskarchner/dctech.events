#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib/core';
import { DctechEventsStack } from '../lib/dctech-events-stack';
import { DcstemEventsStack } from '../lib/dcstem-events-stack';
import { DynamoDBStack } from '../lib/dynamodb-stack';
import { CognitoStack } from '../lib/cognito-stack';
import { SecretsStack } from '../lib/secrets-stack';
import { LambdaApiStack } from '../lib/lambda-api-stack';
import { FrontendStack } from '../lib/frontend-stack';
import { RedirectStack } from '../lib/redirect-stack';
import { stackConfig, dcstemStackConfig } from '../lib/config';

const app = new cdk.App();
const env = { region: stackConfig.region };

// Existing main stack (S3, CloudFront, Route53, DcTechEvents table, GitHub OIDC)
const mainStack = new DctechEventsStack(app, stackConfig.stackName, {
  description: stackConfig.stackDescription,
  env,
});

// New DC STEM Events stack (S3, CloudFront, Route53 - shares backend with dctech)
const dcstemStack = new DcstemEventsStack(app, dcstemStackConfig.stackName, {
  description: dcstemStackConfig.stackDescription,
  env,
});

// Domain redirects (dctechevents.com -> dctech.events)
new RedirectStack(app, `${stackConfig.stackName}-redirects`, {
  env,
});

// Config table (single-table design with DynamoDB Streams)
const dynamoStack = new DynamoDBStack(app, `${stackConfig.stackName}-dynamodb`, {
  env,
  tableName: 'dctech-events',
});

// Cognito authentication
const cognitoStack = new CognitoStack(app, `${stackConfig.stackName}-cognito`, {
  env,
  userPoolName: stackConfig.cognito.userPoolName,
  customDomain: stackConfig.cognito.customDomain,
  certificateArn: stackConfig.acm.existingCertificateArn || mainStack.certificate.certificateArn,
  hostedZoneId: stackConfig.hostedZoneId,
  zoneName: stackConfig.domain,
  callbackUrls: stackConfig.cognito.callbackUrls,
  logoutUrls: stackConfig.cognito.logoutUrls,
  ses: stackConfig.cognito.ses,
  verificationEmail: stackConfig.cognito.verificationEmail,
});

// Secrets Manager
const secretsStack = new SecretsStack(app, `${stackConfig.stackName}-secrets`, {
  env,
  cognitoClientSecretName: stackConfig.secrets.cognitoClientSecret,
  microblogTokenSecretName: stackConfig.secrets.microblogTokenSecret,
  githubTokenSecretName: stackConfig.secrets.githubTokenSecret,
});

// API backend (Lambda + API Gateway)
new LambdaApiStack(app, `${stackConfig.stackName}-api`, {
  env,
  dynamoStack,
  cognitoStack,
  secretsStack,
  materializedTableArn: mainStack.eventsTable.tableArn,
});

// Optional legacy frontend redirects
new FrontendStack(app, `${stackConfig.stackName}-frontend`, {
  env,
  certificate: mainStack.certificate,
});
