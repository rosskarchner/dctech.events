#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib/core';
import { DctechEventsStack } from '../lib/dctech-events-stack';
import { DynamoDBStack } from '../lib/dynamodb-stack';
import { CognitoStack } from '../lib/cognito-stack';
import { SecretsStack } from '../lib/secrets-stack';
import { RebuildStack } from '../lib/rebuild-stack';
import { LambdaApiStack } from '../lib/lambda-api-stack';
import { FrontendStack } from '../lib/frontend-stack';
import { SocialPostingStack } from '../lib/social-posting-stack';
import { stackConfig } from '../lib/config';

const app = new cdk.App();
const env = { region: stackConfig.region };

// Existing main stack (S3, CloudFront, Route53, DcTechEvents table, GitHub OIDC)
const mainStack = new DctechEventsStack(app, stackConfig.stackName, {
  description: stackConfig.stackDescription,
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
});

// Rebuild pipeline (DynamoDB Streams → SQS FIFO → Docker Lambda)
new RebuildStack(app, `${stackConfig.stackName}-rebuild`, {
  env,
  dynamoStack,
  siteBucketName: stackConfig.s3.bucketName,
  dataCacheBucketName: stackConfig.s3.dataCacheBucketName,
  cloudFrontDistributionId: mainStack.distribution.distributionId,
});

// API backend (Lambda + API Gateway)
new LambdaApiStack(app, `${stackConfig.stackName}-api`, {
  env,
  dynamoStack,
  cognitoStack,
  secretsStack,
});

// Frontend apps (suggest.dctech.events, manage.dctech.events)
new FrontendStack(app, `${stackConfig.stackName}-frontend`, {
  env,
  certificate: mainStack.certificate,
});

// Social media automated posting (Micro.blog)
new SocialPostingStack(app, `${stackConfig.stackName}-social-posting`, {
  env,
  microblogTokenSecretArn: secretsStack.microblogTokenSecret.secretArn,
  materializedTableArn: mainStack.eventsTable.tableArn,
  configTableArn: dynamoStack.table.tableArn,
});
