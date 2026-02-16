import * as cdk from 'aws-cdk-lib/core';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';

export interface SecretsStackProps extends cdk.StackProps {
  /**
   * Name of the Cognito client secret in Secrets Manager
   * @default 'dctech-events/cognito-client-secret'
   */
  cognitoClientSecretName?: string;
}

/**
 * Secrets Stack for DC Tech Events
 *
 * Centralized management of application secrets using AWS Secrets Manager.
 * Secrets are created but not populated - values must be set manually after deployment.
 *
 * Secrets managed:
 * 1. Cognito Client Secret: Used for Cognito authentication
 *
 * After deploying this stack, populate secrets using:
 * ```bash
 * aws secretsmanager put-secret-value \
 *   --secret-id dctech-events/cognito-client-secret \
 *   --secret-string '{"client_secret":"YOUR_COGNITO_SECRET"}'
 * ```
 */
export class SecretsStack extends cdk.Stack {
  public readonly cognitoClientSecret: secretsmanager.ISecret;

  constructor(scope: Construct, id: string, props?: SecretsStackProps) {
    super(scope, id, props);

    const secretName = props?.cognitoClientSecretName || 'dctech-events/cognito-client-secret';

    // Create Cognito client secret
    this.cognitoClientSecret = new secretsmanager.Secret(this, 'CognitoClientSecret', {
      secretName: secretName,
      description: 'Cognito User Pool App Client secret for dctech.events authentication',
      secretObjectValue: {
        client_secret: cdk.SecretValue.unsafePlainText('PLACEHOLDER_REPLACE_AFTER_DEPLOYMENT'),
      },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // Stack outputs
    new cdk.CfnOutput(this, 'CognitoClientSecretArn', {
      value: this.cognitoClientSecret.secretArn,
      description: 'ARN of Cognito client secret',
      exportName: 'DctechEventsCognitoClientSecretArn',
    });

    // Apply tags
    cdk.Tags.of(this).add('project', 'dctech-events');
    cdk.Tags.of(this).add('component', 'secrets');
    cdk.Tags.of(this).add('managedBy', 'CDK');
  }
}
