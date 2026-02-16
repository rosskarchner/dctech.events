import * as cdk from 'aws-cdk-lib/core';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as route53Targets from 'aws-cdk-lib/aws-route53-targets';
import { Construct } from 'constructs';

export interface CognitoStackProps extends cdk.StackProps {
  /**
   * Name of the Cognito User Pool
   * @default 'dctech-events-users'
   */
  userPoolName?: string;

  /**
   * Custom domain for Cognito Hosted UI (e.g., 'login.dctech.events')
   * If not specified, falls back to Cognito prefix domain
   */
  customDomain?: string;

  /**
   * Domain prefix for Cognito Hosted UI (fallback if no custom domain)
   * Must be unique across AWS
   * @default 'dctech-events'
   */
  domainPrefix?: string;

  /**
   * ARN of the ACM certificate for the custom domain
   * Required if customDomain is set
   */
  certificateArn?: string;

  /**
   * Route53 Hosted Zone ID for DNS records
   * Required if customDomain is set
   */
  hostedZoneId?: string;

  /**
   * Root domain name (e.g., 'dctech.events')
   * Required if customDomain is set
   */
  zoneName?: string;

  /**
   * Callback URLs for OAuth redirect after authentication
   * @default ['http://localhost:5000/auth/callback']
   */
  callbackUrls?: string[];

  /**
   * Logout URLs for OAuth redirect after sign out
   * @default ['http://localhost:5000/']
   */
  logoutUrls?: string[];

  /**
   * Removal policy for the Cognito User Pool
   * @default cdk.RemovalPolicy.RETAIN (production-safe)
   */
  removalPolicy?: cdk.RemovalPolicy;
}

/**
 * Cognito Stack for DC Tech Events Authentication
 *
 * Provides user authentication and authorization with:
 * - User Pool: Manages user accounts and profiles
 * - App Client: OAuth 2.0/OIDC integration
 * - Hosted UI: Pre-built login/signup pages
 * - User Groups: Admin role assignment
 * - Custom domain: login.dctech.events (using existing wildcard cert)
 */
export class CognitoStack extends cdk.Stack {
  public readonly userPool: cognito.UserPool;
  public readonly userPoolClient: cognito.UserPoolClient;
  public readonly userPoolDomain: cognito.UserPoolDomain;

  constructor(scope: Construct, id: string, props?: CognitoStackProps) {
    super(scope, id, props);

    const userPoolName = props?.userPoolName || 'dctech-events-users';
    const callbackUrls = props?.callbackUrls || ['http://localhost:5000/auth/callback'];
    const logoutUrls = props?.logoutUrls || ['http://localhost:5000/'];
    const removalPolicy = props?.removalPolicy || cdk.RemovalPolicy.RETAIN;

    // Create Cognito User Pool
    this.userPool = new cognito.UserPool(this, 'DctechEventsUserPool', {
      userPoolName: userPoolName,

      signInAliases: {
        email: true,
        username: false,
      },

      selfSignUpEnabled: true,

      autoVerify: {
        email: true,
      },

      standardAttributes: {
        email: {
          required: true,
          mutable: false,
        },
        fullname: {
          required: false,
          mutable: true,
        },
      },

      customAttributes: {
        'submissions_count': new cognito.NumberAttribute({ min: 0, max: 10000, mutable: true }),
        'approved_count': new cognito.NumberAttribute({ min: 0, max: 10000, mutable: true }),
      },

      passwordPolicy: {
        minLength: 8,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: false,
        tempPasswordValidity: cdk.Duration.days(7),
      },

      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,

      email: cognito.UserPoolEmail.withCognito(),

      mfa: cognito.Mfa.OPTIONAL,
      mfaSecondFactor: {
        sms: false,
        otp: true,
      },

      removalPolicy: removalPolicy,
    });

    // Create Admin user group
    new cognito.CfnUserPoolGroup(this, 'AdminGroup', {
      userPoolId: this.userPool.userPoolId,
      groupName: 'admins',
      description: 'Administrators who can approve/reject submissions and edit content',
      precedence: 1,
    });

    // Create User Pool App Client for OAuth 2.0
    this.userPoolClient = this.userPool.addClient('DctechEventsAppClient', {
      userPoolClientName: 'dctech-events-web',

      oAuth: {
        flows: {
          authorizationCodeGrant: true,
          implicitCodeGrant: false,
        },

        scopes: [
          cognito.OAuthScope.EMAIL,
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.PROFILE,
        ],

        callbackUrls: callbackUrls,
        logoutUrls: logoutUrls,
      },

      idTokenValidity: cdk.Duration.hours(1),
      accessTokenValidity: cdk.Duration.hours(1),
      refreshTokenValidity: cdk.Duration.days(30),

      authFlows: {
        userPassword: true,
        userSrp: true,
        custom: false,
        adminUserPassword: false,
      },

      preventUserExistenceErrors: true,

      readAttributes: new cognito.ClientAttributes()
        .withStandardAttributes({ email: true, emailVerified: true, fullname: true })
        .withCustomAttributes('submissions_count', 'approved_count'),
      writeAttributes: new cognito.ClientAttributes()
        .withStandardAttributes({ fullname: true, email: true }),
    });

    // Configure domain - prefer custom domain, fall back to prefix
    if (props?.customDomain && props?.certificateArn && props?.hostedZoneId && props?.zoneName) {
      const certificate = acm.Certificate.fromCertificateArn(this, 'CustomDomainCert', props.certificateArn);
      this.userPoolDomain = this.userPool.addDomain('DctechEventsCustomDomain', {
        customDomain: {
          domainName: props.customDomain,
          certificate: certificate,
        },
      });

      // Create Route53 A record for custom domain
      const hostedZone = route53.HostedZone.fromHostedZoneAttributes(this, 'HostedZone', {
        hostedZoneId: props.hostedZoneId,
        zoneName: props.zoneName,
      });

      new route53.ARecord(this, 'CognitoCustomDomainARecord', {
        zone: hostedZone,
        recordName: props.customDomain,
        target: route53.RecordTarget.fromAlias(
          new route53Targets.UserPoolDomainTarget(this.userPoolDomain)
        ),
      });
    } else {
      const domainPrefix = props?.domainPrefix || 'dctech-events';
      this.userPoolDomain = this.userPool.addDomain('DctechEventsDomain', {
        cognitoDomain: {
          domainPrefix: domainPrefix,
        },
      });
    }

    // Stack outputs
    new cdk.CfnOutput(this, 'UserPoolId', {
      value: this.userPool.userPoolId,
      description: 'Cognito User Pool ID',
      exportName: 'DctechEventsUserPoolId',
    });

    new cdk.CfnOutput(this, 'UserPoolArn', {
      value: this.userPool.userPoolArn,
      description: 'Cognito User Pool ARN',
      exportName: 'DctechEventsUserPoolArn',
    });

    new cdk.CfnOutput(this, 'UserPoolClientId', {
      value: this.userPoolClient.userPoolClientId,
      description: 'Cognito User Pool App Client ID',
      exportName: 'DctechEventsUserPoolClientId',
    });

    new cdk.CfnOutput(this, 'UserPoolDomainUrl', {
      value: this.userPoolDomain.baseUrl(),
      description: 'Cognito Hosted UI URL',
      exportName: 'DctechEventsHostedUiUrl',
    });

    // Apply tags
    cdk.Tags.of(this).add('project', 'dctech-events');
    cdk.Tags.of(this).add('component', 'authentication');
    cdk.Tags.of(this).add('managedBy', 'CDK');
  }
}
