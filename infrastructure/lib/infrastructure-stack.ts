import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as eventbridge from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as certificatemanager from 'aws-cdk-lib/aws-certificatemanager';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';

export interface OrganizeDCTechStackProps extends cdk.StackProps {
  domainName?: string;
  certificateArn?: string;
  hostedZoneId?: string;
}

export class InfrastructureStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: OrganizeDCTechStackProps) {
    super(scope, id, props);

    // ============================================
    // Cognito User Pool for Authentication
    // ============================================
    const userPool = new cognito.UserPool(this, 'OrganizeUserPool', {
      userPoolName: 'organize-dctech-events-users',
      selfSignUpEnabled: true,
      signInAliases: {
        email: true,
        username: true,
      },
      autoVerify: {
        email: true,
      },
      standardAttributes: {
        email: {
          required: true,
          mutable: true,
        },
        fullname: {
          required: true,
          mutable: true,
        },
      },
      customAttributes: {
        bio: new cognito.StringAttribute({ minLen: 0, maxLen: 500, mutable: true }),
        website: new cognito.StringAttribute({ minLen: 0, maxLen: 200, mutable: true }),
      },
      passwordPolicy: {
        minLength: 8,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: false,
      },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const userPoolClient = new cognito.UserPoolClient(this, 'OrganizeUserPoolClient', {
      userPool,
      authFlows: {
        userPassword: true,
        userSrp: true,
      },
      generateSecret: false,
      oAuth: {
        flows: {
          authorizationCodeGrant: true,
          implicitCodeGrant: true,
        },
        scopes: [
          cognito.OAuthScope.EMAIL,
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.PROFILE,
        ],
        callbackUrls: props?.domainName
          ? [`https://${props.domainName}/callback`, 'http://localhost:3000/callback']
          : ['http://localhost:3000/callback'],
        logoutUrls: props?.domainName
          ? [`https://${props.domainName}`, 'http://localhost:3000']
          : ['http://localhost:3000'],
      },
    });

    const userPoolDomain = userPool.addDomain('OrganizeUserPoolDomain', {
      cognitoDomain: {
        domainPrefix: 'organize-dctech-events',
      },
    });

    // ============================================
    // DynamoDB Tables
    // ============================================

    // Users table (for extended profile info beyond Cognito)
    const usersTable = new dynamodb.Table(this, 'UsersTable', {
      tableName: 'organize-users',
      partitionKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
    });

    // Groups table
    const groupsTable = new dynamodb.Table(this, 'GroupsTable', {
      tableName: 'organize-groups',
      partitionKey: { name: 'groupId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
    });

    // Add GSI for active groups
    groupsTable.addGlobalSecondaryIndex({
      indexName: 'activeGroupsIndex',
      partitionKey: { name: 'active', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'createdAt', type: dynamodb.AttributeType.STRING },
    });

    // Group Members table
    const groupMembersTable = new dynamodb.Table(this, 'GroupMembersTable', {
      tableName: 'organize-group-members',
      partitionKey: { name: 'groupId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
    });

    // Add GSI for user's groups
    groupMembersTable.addGlobalSecondaryIndex({
      indexName: 'userGroupsIndex',
      partitionKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'groupId', type: dynamodb.AttributeType.STRING },
    });

    // Events table
    const eventsTable = new dynamodb.Table(this, 'EventsTable', {
      tableName: 'organize-events',
      partitionKey: { name: 'eventId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
    });

    // Add GSI for events by group
    eventsTable.addGlobalSecondaryIndex({
      indexName: 'groupEventsIndex',
      partitionKey: { name: 'groupId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'eventDate', type: dynamodb.AttributeType.STRING },
    });

    // Add GSI for events by date
    eventsTable.addGlobalSecondaryIndex({
      indexName: 'dateEventsIndex',
      partitionKey: { name: 'eventType', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'eventDate', type: dynamodb.AttributeType.STRING },
    });

    // RSVPs table
    const rsvpsTable = new dynamodb.Table(this, 'RSVPsTable', {
      tableName: 'organize-rsvps',
      partitionKey: { name: 'eventId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
    });

    // Add GSI for user's RSVPs
    rsvpsTable.addGlobalSecondaryIndex({
      indexName: 'userRSVPsIndex',
      partitionKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'eventId', type: dynamodb.AttributeType.STRING },
    });

    // Messages table
    const messagesTable = new dynamodb.Table(this, 'MessagesTable', {
      tableName: 'organize-messages',
      partitionKey: { name: 'groupId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'timestamp', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
    });

    // ============================================
    // S3 Bucket for Static Website and Exports
    // ============================================
    const websiteBucket = new s3.Bucket(this, 'OrganizeWebsiteBucket', {
      bucketName: 'organize-dctech-events',
      websiteIndexDocument: 'index.html',
      websiteErrorDocument: 'index.html',
      publicReadAccess: false,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      cors: [
        {
          allowedOrigins: ['*'],
          allowedMethods: [s3.HttpMethods.GET],
          allowedHeaders: ['*'],
        },
      ],
    });

    // OAI for CloudFront to access S3
    const originAccessIdentity = new cloudfront.OriginAccessIdentity(
      this,
      'OrganizeOAI',
      {
        comment: 'OAI for organize.dctech.events',
      }
    );

    websiteBucket.grantRead(originAccessIdentity);

    // ============================================
    // CloudFront Distribution
    // ============================================
    const distribution = new cloudfront.Distribution(this, 'OrganizeDistribution', {
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessIdentity(websiteBucket, {
          originAccessIdentity,
        }),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD,
        cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD,
      },
      defaultRootObject: 'index.html',
      errorResponses: [
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
        },
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
        },
      ],
      domainNames: props?.domainName ? [props.domainName] : undefined,
      certificate: props?.certificateArn
        ? certificatemanager.Certificate.fromCertificateArn(
            this,
            'Certificate',
            props.certificateArn
          )
        : undefined,
    });

    // ============================================
    // Lambda Functions for API
    // ============================================

    // Environment variables for Lambda functions
    const lambdaEnv = {
      USERS_TABLE: usersTable.tableName,
      GROUPS_TABLE: groupsTable.tableName,
      GROUP_MEMBERS_TABLE: groupMembersTable.tableName,
      EVENTS_TABLE: eventsTable.tableName,
      RSVPS_TABLE: rsvpsTable.tableName,
      MESSAGES_TABLE: messagesTable.tableName,
      USER_POOL_ID: userPool.userPoolId,
      WEBSITE_BUCKET: websiteBucket.bucketName,
    };

    // API Lambda function (handles all API routes)
    const apiFunction = new lambda.Function(this, 'ApiFunction', {
      runtime: lambda.Runtime.NODEJS_20_X,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('lambda/api'),
      environment: lambdaEnv,
      timeout: cdk.Duration.seconds(30),
      memorySize: 512,
    });

    // Grant permissions to Lambda
    usersTable.grantReadWriteData(apiFunction);
    groupsTable.grantReadWriteData(apiFunction);
    groupMembersTable.grantReadWriteData(apiFunction);
    eventsTable.grantReadWriteData(apiFunction);
    rsvpsTable.grantReadWriteData(apiFunction);
    messagesTable.grantReadWriteData(apiFunction);

    // Grant Cognito permissions
    apiFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['cognito-idp:GetUser', 'cognito-idp:AdminGetUser'],
        resources: [userPool.userPoolArn],
      })
    );

    // Export Lambda function (generates groups.yaml and events.yaml)
    const exportFunction = new lambda.Function(this, 'ExportFunction', {
      runtime: lambda.Runtime.NODEJS_20_X,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('lambda/export'),
      environment: lambdaEnv,
      timeout: cdk.Duration.minutes(5),
      memorySize: 1024,
    });

    // Grant permissions to export Lambda
    groupsTable.grantReadData(exportFunction);
    eventsTable.grantReadData(exportFunction);
    websiteBucket.grantWrite(exportFunction);

    // Schedule export to run every 5 minutes
    const exportRule = new eventbridge.Rule(this, 'ExportSchedule', {
      schedule: eventbridge.Schedule.rate(cdk.Duration.minutes(5)),
    });
    exportRule.addTarget(new targets.LambdaFunction(exportFunction));

    // ============================================
    // API Gateway
    // ============================================
    const api = new apigateway.RestApi(this, 'OrganizeApi', {
      restApiName: 'Organize DC Tech Events API',
      description: 'API for organize.dctech.events',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: [
          'Content-Type',
          'X-Amz-Date',
          'Authorization',
          'X-Api-Key',
          'X-Amz-Security-Token',
        ],
      },
    });

    // Cognito authorizer
    const authorizer = new apigateway.CognitoUserPoolsAuthorizer(
      this,
      'CognitoAuthorizer',
      {
        cognitoUserPools: [userPool],
      }
    );

    // Lambda integration
    const apiIntegration = new apigateway.LambdaIntegration(apiFunction);

    // Use proxy resource to avoid Lambda permission policy size limits
    // This creates a single permission instead of one per route
    // The Lambda function handles all routing and authentication internally
    // Note: Authorizer is removed to support both public and protected routes
    // The Lambda validates Cognito tokens when present and checks permissions per route
    const proxy = api.root.addResource('{proxy+}');
    proxy.addMethod('ANY', apiIntegration);

    // ============================================
    // Outputs
    // ============================================
    new cdk.CfnOutput(this, 'UserPoolId', {
      value: userPool.userPoolId,
      description: 'Cognito User Pool ID',
    });

    new cdk.CfnOutput(this, 'UserPoolClientId', {
      value: userPoolClient.userPoolClientId,
      description: 'Cognito User Pool Client ID',
    });

    new cdk.CfnOutput(this, 'UserPoolDomain', {
      value: userPoolDomain.domainName,
      description: 'Cognito User Pool Domain',
    });

    new cdk.CfnOutput(this, 'ApiUrl', {
      value: api.url,
      description: 'API Gateway URL',
    });

    new cdk.CfnOutput(this, 'CloudFrontUrl', {
      value: distribution.distributionDomainName,
      description: 'CloudFront Distribution URL',
    });

    new cdk.CfnOutput(this, 'WebsiteBucketName', {
      value: websiteBucket.bucketName,
      description: 'S3 Website Bucket Name',
    });

    new cdk.CfnOutput(this, 'GroupsYamlUrl', {
      value: `https://${distribution.distributionDomainName}/groups.yaml`,
      description: 'URL for groups.yaml export',
    });

    new cdk.CfnOutput(this, 'EventsYamlUrl', {
      value: `https://${distribution.distributionDomainName}/events.yaml`,
      description: 'URL for events.yaml export',
    });
  }
}
