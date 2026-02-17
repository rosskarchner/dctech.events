import * as cdk from 'aws-cdk-lib/core';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';

export interface SecretsStackProps extends cdk.StackProps {
  /**
   * Name of the Cognito client secret in Secrets Manager
   * @default 'dctech-events/cognito-client-secret'
   */
  cognitoClientSecretName?: string;

  /**
   * Name of the Micro.blog token secret
   * @default 'dctech-events/microblog-token'
   */
  microblogTokenSecretName?: string;
}

/**
 * Secrets Stack for DC Tech Events
 *
 * Centralized management of application secrets using AWS Secrets Manager.
 * Secrets are created but not populated - values must be set manually after deployment.
 *
 * Secrets managed:
 * 1. Cognito Client Secret: Used for Cognito authentication
 * 2. Micro.blog Token: Used for automated posting to Micro.blog
 *
 * After deploying this stack, populate secrets using:
 * ```bash
 * aws secretsmanager put-secret-value \
 *   --secret-id dctech-events/microblog-token \
 *   --secret-string "YOUR_TOKEN"
 * ```
 */
export class SecretsStack extends cdk.Stack {
  public readonly cognitoClientSecret: secretsmanager.ISecret;
  public readonly microblogTokenSecret: secretsmanager.ISecret;

  constructor(scope: Construct, id: string, props?: SecretsStackProps) {
    super(scope, id, props);

    const secretName = props?.cognitoClientSecretName || 'dctech-events/cognito-client-secret';
    const mbTokenSecretName = props?.microblogTokenSecretName || 'dctech-events/microblog-token';

    // Create Cognito client secret
    this.cognitoClientSecret = new secretsmanager.Secret(this, 'CognitoClientSecret', {
      secretName: secretName,
      description: 'Cognito User Pool App Client secret for dctech.events authentication',
      secretObjectValue: {
        client_secret: cdk.SecretValue.unsafePlainText('PLACEHOLDER_REPLACE_AFTER_DEPLOYMENT'),
      },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // Create Micro.blog token secret
    this.microblogTokenSecret = new secretsmanager.Secret(this, 'MicroblogTokenSecret', {
      secretName: mbTokenSecretName,
      description: 'API Token for Micro.blog automated posting',
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // Stack outputs
    new cdk.CfnOutput(this, 'CognitoClientSecretArn', {
      value: this.cognitoClientSecret.secretArn,
      description: 'ARN of Cognito client secret',
      exportName: 'DctechEventsCognitoClientSecretArn',
    });

    new cdk.CfnOutput(this, 'MicroblogTokenSecretArn', {
      value: this.microblogTokenSecret.secretArn,
      description: 'ARN of Micro.blog token secret',
      exportName: 'DctechEventsMicroblogTokenSecretArn',
    });

    // Apply tags
    cdk.Tags.of(this).add('project', 'dctech-events');
    cdk.Tags.of(this).add('component', 'secrets');
    cdk.Tags.of(this).add('managedBy', 'CDK');
  }
}
