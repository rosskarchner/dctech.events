import * as cdk from 'aws-cdk-lib/core';
import { SecretsStack } from './secrets-stack';
import { CognitoStack } from './cognito-stack';
import { DynamoDBStack } from './dynamodb-stack';

/**
 * Stack properties for LambdaApiStack
 */
export interface LambdaApiStackProps extends cdk.StackProps {
  /**
   * Reference to the SecretsStack for accessing Cognito client secret
   */
  secretsStack: SecretsStack;

  /**
   * Reference to the CognitoStack for User Pool and Client IDs
   */
  cognitoStack: CognitoStack;

  /**
   * Reference to the DynamoDBStack for table name and permissions
   */
  dynamoStack: DynamoDBStack;

  /**
   * Cognito domain prefix
   * @default 'dctech-events'
   */
  cognitoDomain?: string;

  /**
   * Stage name for deployment
   * @default 'prod'
   */
  stageName?: string;

  /**
   * Python runtime version
   * @default 'python3.12'
   */
  runtime?: string;

  /**
   * Lambda memory size in MB
   * @default 512
   */
  memorySize?: number;

  /**
   * Lambda timeout in seconds
   * @default 30
   */
  timeout?: number;
}

/**
 * Stack properties for OAuthEndpointStack
 */
export interface OAuthEndpointStackProps extends cdk.StackProps {
  /**
   * Reference to the SecretsStack for GitHub OAuth secret
   */
  secretsStack: SecretsStack;
}
