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
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as route53targets from 'aws-cdk-lib/aws-route53-targets';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';

export interface OrganizeDCTechStackProps extends cdk.StackProps {
  domainName?: string;
  certificateArn?: string;
  hostedZoneId?: string;
  cognitoDomainPrefix?: string;
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
          ? [
              `https://${props.domainName}/callback`,
              'https://next.dctech.events/callback',
              'http://localhost:3000/callback'
            ]
          : ['http://localhost:3000/callback'],
        logoutUrls: props?.domainName
          ? [
              `https://${props.domainName}`,
              'https://next.dctech.events',
              'http://localhost:3000'
            ]
          : ['http://localhost:3000'],
      },
    });

    // Use provided domain prefix or generate one with account ID for uniqueness
    // Cognito domain prefixes must be globally unique across all AWS regions
    const cognitoDomainPrefix = props?.cognitoDomainPrefix || 
      `organize-dctech-${cdk.Stack.of(this).account}`;

    const userPoolDomain = userPool.addDomain('OrganizeUserPoolDomain', {
      cognitoDomain: {
        domainPrefix: cognitoDomainPrefix,
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

    // Origin Access Control for CloudFront to access S3
    const originAccessControl = new cloudfront.S3OriginAccessControl(this, 'OrganizeOAC', {
      description: 'OAC for organize.dctech.events',
    });
    
    const nextOriginAccessControl = new cloudfront.S3OriginAccessControl(this, 'NextOAC', {
      description: 'OAC for next.dctech.events static assets',
    });

    // ============================================
    // Route 53 and SSL Certificate
    // ============================================

    // Look up the existing hosted zone for dctech.events
    const hostedZone = route53.HostedZone.fromLookup(this, 'DcTechHostedZone', {
      domainName: 'dctech.events',
    });

    // Create or reference ACM certificate for organize.dctech.events
    // Must be in us-east-1 for CloudFront
    let certificate: certificatemanager.ICertificate;
    if (props?.certificateArn) {
      // Reference existing certificate in us-east-1
      certificate = certificatemanager.Certificate.fromCertificateArn(
        this,
        'OrganizeCertificate',
        props.certificateArn
      );
    } else {
      // Validate region is us-east-1 before creating certificate
      if (cdk.Stack.of(this).region !== 'us-east-1') {
        throw new Error(
          'ACM certificates for CloudFront must be created in us-east-1. ' +
          'Provide a certificateArn for a certificate in us-east-1, or deploy this stack to us-east-1.'
        );
      }
      certificate = new certificatemanager.Certificate(this, 'OrganizeCertificate', {
        domainName: 'organize.dctech.events',
        validation: certificatemanager.CertificateValidation.fromDns(hostedZone),
      });
    }

    // Create ACM certificate for next.dctech.events (must be in us-east-1 for CloudFront)
    let nextCertificate: certificatemanager.ICertificate;
    if (cdk.Stack.of(this).region !== 'us-east-1') {
      throw new Error(
        'ACM certificates for CloudFront must be created in us-east-1. ' +
        'Deploy this stack to us-east-1.'
      );
    }
    nextCertificate = new certificatemanager.Certificate(this, 'NextDcTechCertificate', {
      domainName: 'next.dctech.events',
      validation: certificatemanager.CertificateValidation.fromDns(hostedZone),
    });

    // ============================================
    // CloudFront Distribution
    // ============================================
    const distribution = new cloudfront.Distribution(this, 'OrganizeDistribution', {
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(websiteBucket, {
          originAccessControl,
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
      domainNames: ['organize.dctech.events'],
      certificate: certificate,
    });

    // Grant CloudFront OAC read access to S3 bucket
    websiteBucket.addToResourcePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      principals: [new iam.ServicePrincipal('cloudfront.amazonaws.com')],
      actions: ['s3:GetObject'],
      resources: [websiteBucket.arnForObjects('*')],
      conditions: {
        StringEquals: {
          'AWS:SourceArn': `arn:aws:cloudfront::${this.account}:distribution/${distribution.distributionId}`,
        },
      },
    }));

    // ============================================
    // Route 53 DNS Records
    // ============================================

    // Create A record for organize.dctech.events pointing to CloudFront
    new route53.ARecord(this, 'OrganizeARecord', {
      zone: hostedZone,
      recordName: 'organize',
      target: route53.RecordTarget.fromAlias(
        new route53targets.CloudFrontTarget(distribution)
      ),
    });

    // Create AAAA record for IPv6 support
    new route53.AaaaRecord(this, 'OrganizeAAAARecord', {
      zone: hostedZone,
      recordName: 'organize',
      target: route53.RecordTarget.fromAlias(
        new route53targets.CloudFrontTarget(distribution)
      ),
    });

    // ============================================
    // CloudFront Distribution for next.dctech.events
    // ============================================

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
      USER_POOL_CLIENT_ID: userPoolClient.userPoolClientId,
      USER_POOL_REGION: cdk.Stack.of(this).region,
      WEBSITE_BUCKET: websiteBucket.bucketName,
      NEXT_DCTECH_DOMAIN: this.node.tryGetContext('nextDomain') || 'next.dctech.events',
      ORGANIZE_DOMAIN: this.node.tryGetContext('organizeDomain') || 'organize.dctech.events',
      GITHUB_REPO: this.node.tryGetContext('githubRepo') || 'rosskarchner/dctech.events',
    };

    // Lambda Layer for Handlebars templates
    const templatesLayer = new lambda.LayerVersion(this, 'TemplatesLayer', {
      code: lambda.Code.fromAsset('infrastructure/lambda/layers/templates'),
      compatibleRuntimes: [lambda.Runtime.NODEJS_20_X],
      description: 'Handlebars templates for both organize and next.dctech.events',
    });

    // API Lambda function (handles all API routes)
    const apiFunction = new lambda.Function(this, 'ApiFunction', {
      runtime: lambda.Runtime.NODEJS_20_X,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('lambda/api'),
      environment: lambdaEnv,
      timeout: cdk.Duration.seconds(30),
      memorySize: 512,
      tracing: lambda.Tracing.ACTIVE, // Enable X-Ray tracing
      layers: [templatesLayer],
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
      tracing: lambda.Tracing.ACTIVE, // Enable X-Ray tracing
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

    // Refresh Lambda function (syncs groups/events from GitHub and fetches iCal feeds)
    const refreshFunction = new lambda.Function(this, 'RefreshFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'lambda_function.lambda_handler',
      code: lambda.Code.fromAsset('infrastructure/lambda/refresh'),
      environment: {
        ...lambdaEnv,
        GITHUB_TOKEN_SECRET: 'dctech-events/github-token',
      },
      timeout: cdk.Duration.minutes(5),
      memorySize: 1024,
      description: 'Fetches iCal feeds and syncs from GitHub repo',
      tracing: lambda.Tracing.ACTIVE,
    });

    // Grant permissions to refresh Lambda
    groupsTable.grantReadWriteData(refreshFunction);
    eventsTable.grantReadWriteData(refreshFunction);

    // Grant permission to read GitHub token from Secrets Manager
    refreshFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['secretsmanager:GetSecretValue'],
        resources: [`arn:aws:secretsmanager:${this.region}:${this.account}:secret:dctech-events/github-token-*`],
      })
    );

    // Schedule refresh to run every 4 hours
    const refreshRule = new eventbridge.Rule(this, 'RefreshSchedule', {
      schedule: eventbridge.Schedule.rate(cdk.Duration.hours(4)),
      description: 'Refresh iCal feeds from 110+ groups and sync from GitHub',
    });
    refreshRule.addTarget(new targets.LambdaFunction(refreshFunction));

    // ============================================
    // CloudWatch Alarms for Monitoring
    // ============================================

    // API Lambda error alarm
    const apiErrorAlarm = new cloudwatch.Alarm(this, 'ApiLambdaErrorAlarm', {
      metric: apiFunction.metricErrors({
        statistic: 'Sum',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 10,
      evaluationPeriods: 1,
      alarmDescription: 'Alert when API Lambda function has more than 10 errors in 5 minutes',
      alarmName: 'organize-api-lambda-errors',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // Export Lambda error alarm
    const exportErrorAlarm = new cloudwatch.Alarm(this, 'ExportLambdaErrorAlarm', {
      metric: exportFunction.metricErrors({
        statistic: 'Sum',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 3,
      evaluationPeriods: 2,
      alarmDescription: 'Alert when Export Lambda function has more than 3 errors in 10 minutes',
      alarmName: 'organize-export-lambda-errors',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // DynamoDB throttle alarms for critical tables
    const groupsThrottleAlarm = new cloudwatch.Alarm(this, 'GroupsTableThrottleAlarm', {
      metric: groupsTable.metricUserErrors({
        statistic: 'Sum',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 5,
      evaluationPeriods: 2,
      alarmDescription: 'Alert when Groups table experiences throttling',
      alarmName: 'organize-groups-table-throttle',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    const eventsThrottleAlarm = new cloudwatch.Alarm(this, 'EventsTableThrottleAlarm', {
      metric: eventsTable.metricUserErrors({
        statistic: 'Sum',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 5,
      evaluationPeriods: 2,
      alarmDescription: 'Alert when Events table experiences throttling',
      alarmName: 'organize-events-table-throttle',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // ============================================
    // API Gateway
    // ============================================
    const api = new apigateway.RestApi(this, 'OrganizeApi', {
      restApiName: 'Organize DC Tech Events API',
      description: 'API for organize.dctech.events',
      defaultCorsPreflightOptions: {
        allowOrigins: [
          'https://organize.dctech.events',
          'http://localhost:3000', // For local development
        ],
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: [
          'Content-Type',
          'X-Amz-Date',
          'Authorization',
          'X-Api-Key',
          'X-Amz-Security-Token',
          'HX-Request',
          'HX-Target',
          'HX-Trigger',
        ],
      },
    });

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
    // CloudFront Distribution for next.dctech.events
    // ============================================

    const nextDistribution = new cloudfront.Distribution(this, 'NextDcTechDistribution', {
      defaultBehavior: {
        origin: new origins.HttpOrigin(`${api.restApiId}.execute-api.${this.region}.amazonaws.com`, {
          originPath: '/prod',
          customHeaders: {
            'X-Site': 'next',
          },
        }),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
        cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED, // Disable caching for dynamic content
      },
      additionalBehaviors: {
        '/static/*': {
          origin: origins.S3BucketOrigin.withOriginAccessControl(websiteBucket, {
            originAccessControl: nextOriginAccessControl,
          }),
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        },
      },
      domainNames: ['next.dctech.events'],
      certificate: nextCertificate,
    });

    // Grant CloudFront OAC read access to S3 bucket for next distribution static assets
    websiteBucket.addToResourcePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      principals: [new iam.ServicePrincipal('cloudfront.amazonaws.com')],
      actions: ['s3:GetObject'],
      resources: [websiteBucket.arnForObjects('*')],
      conditions: {
        StringEquals: {
          'AWS:SourceArn': `arn:aws:cloudfront::${this.account}:distribution/${nextDistribution.distributionId}`,
        },
      },
    }));

    // Add Route 53 A & AAAA records for next.dctech.events
    new route53.ARecord(this, 'NextDcTechARecord', {
      zone: hostedZone,
      recordName: 'next',
      target: route53.RecordTarget.fromAlias(
        new route53targets.CloudFrontTarget(nextDistribution)
      ),
    });

    new route53.AaaaRecord(this, 'NextDcTechAaaaRecord', {
      zone: hostedZone,
      recordName: 'next',
      target: route53.RecordTarget.fromAlias(
        new route53targets.CloudFrontTarget(nextDistribution)
      ),
    });

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
