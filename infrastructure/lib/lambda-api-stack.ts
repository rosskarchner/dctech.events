import * as cdk from 'aws-cdk-lib/core';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as route53targets from 'aws-cdk-lib/aws-route53-targets';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import { LambdaApiStackProps } from './interfaces';
import { stackConfig } from './config';
import * as path from 'path';
import { execSync } from 'child_process';

/**
 * Lambda API Stack for DC Tech Events
 *
 * Deploys the Python application as a Lambda function with API Gateway REST API.
 * Replaces Chalice with native CDK constructs for better control and Python 3.14 compatibility.
 */
export class LambdaApiStack extends cdk.Stack {
  public readonly apiEndpoint: string;
  public readonly customDomainName?: apigateway.DomainName;
  public readonly apiFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: LambdaApiStackProps) {
    super(scope, id, props);

    const stageName = props.stageName || stackConfig.chalice.mainApi.stageName;
    const cognitoDomain = props.cognitoDomain || stackConfig.cognito.domainPrefix;
    const region = props.env?.region || stackConfig.region;
    const apiDomain = 'next.dctech.events';
    const baseDomain = 'dctech.events';

    // Create Lambda execution role
    const lambdaRole = new iam.Role(this, 'ApiLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: 'Execution role for dctech-events API Lambda',
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Add DynamoDB permissions
    lambdaRole.addToPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'dynamodb:GetItem',
        'dynamodb:PutItem',
        'dynamodb:UpdateItem',
        'dynamodb:DeleteItem',
        'dynamodb:Query',
        'dynamodb:Scan',
        'dynamodb:BatchGetItem',
        'dynamodb:BatchWriteItem',
      ],
      resources: [
        props.dynamoStack.table.tableArn,
        `${props.dynamoStack.table.tableArn}/index/*`,
      ],
    }));

    // Add Secrets Manager permissions
    lambdaRole.addToPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['secretsmanager:GetSecretValue'],
      resources: [props.secretsStack.cognitoClientSecret.secretArn],
    }));

    // Create Lambda function
    this.apiFunction = new lambda.Function(this, 'ApiFunction', {
      functionName: 'dctech-events-api',
      runtime: lambda.Runtime.PYTHON_3_12, // Use 3.12 (supported)
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../backend'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -r requirements.txt -t /asset-output && cp -au . /asset-output',
          ],
          local: {
            tryBundle(outputDir: string) {
              try {
                execSync('python3 -m pip --version');
              } catch {
                return false;
              }

              const commands = [
                `python3 -m pip install -r ${path.join(__dirname, '../../backend/requirements.txt')} -t ${outputDir} --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all: --upgrade`,
                `cp -r ${path.join(__dirname, '../../backend')}/* ${outputDir}`
              ];

              execSync(commands.join(' && '), { stdio: 'inherit' });
              return true;
            },
          },
        },
        exclude: [
          'cdk-output',
          '.chalice',
          '*.pyc',
          '__pycache__',
          'tests',
          '.git',
          '.venv',
          'node_modules',
        ],
      }),
      role: lambdaRole,
      timeout: cdk.Duration.seconds(30),
      memorySize: 512,
      environment: {
        COGNITO_USER_POOL_ID: props.cognitoStack.userPool.userPoolId,
        COGNITO_USER_POOL_CLIENT_ID: props.cognitoStack.userPoolClient.userPoolClientId,
        COGNITO_DOMAIN: cognitoDomain,
        COGNITO_CLIENT_SECRET_NAME: stackConfig.secrets.cognitoClientSecret,
        DYNAMODB_TABLE_NAME: props.dynamoStack.table.tableName,
        STAGE: stageName,
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // Create API Gateway REST API
    const api = new apigateway.RestApi(this, 'Api', {
      restApiName: 'dctech-events-api',
      description: 'DC Tech Events API',
      deployOptions: {
        stageName: stageName,
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        dataTraceEnabled: true,
        metricsEnabled: true,
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'Authorization'],
      },
    });

    // Create Cognito User Pool Authorizer
    const authorizer = new apigateway.CognitoUserPoolsAuthorizer(this, 'CognitoAuthorizer', {
      cognitoUserPools: [props.cognitoStack.userPool],
      identitySource: 'method.request.header.Authorization',
    });

    // Create Lambda integration
    const lambdaIntegration = new apigateway.LambdaIntegration(this.apiFunction, {
      proxy: true,
      allowTestInvoke: true,
    });

    // Add routes

    // Public routes (no auth)
    const health = api.root.addResource('health');
    health.addMethod('GET', lambdaIntegration);

    const apiResource = api.root.addResource('api');

    const events = apiResource.addResource('events');
    events.addMethod('GET', lambdaIntegration); // Public API

    const upcomingIcs = events.addResource('upcoming.ics');
    upcomingIcs.addMethod('GET', lambdaIntegration);

    const overrides = apiResource.addResource('overrides');
    overrides.addMethod('GET', lambdaIntegration); // Public API

    // Authenticated routes
    const submit = api.root.addResource('submit');
    submit.addMethod('GET', lambdaIntegration, {
      authorizer: authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });
    submit.addMethod('POST', lambdaIntegration, {
      authorizer: authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    // Admin routes
    const admin = api.root.addResource('admin');
    admin.addMethod('GET', lambdaIntegration, {
      authorizer: authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    const queue = admin.addResource('queue');
    queue.addMethod('GET', lambdaIntegration, {
      authorizer: authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    const draft = admin.addResource('draft');
    const draftId = draft.addResource('{draft_id}');
    draftId.addMethod('GET', lambdaIntegration, {
      authorizer: authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });
    draftId.addMethod('PUT', lambdaIntegration, {
      authorizer: authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    const approve = draftId.addResource('approve');
    approve.addMethod('POST', lambdaIntegration, {
      authorizer: authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    const reject = draftId.addResource('reject');
    reject.addMethod('POST', lambdaIntegration, {
      authorizer: authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    const adminOverrides = admin.addResource('overrides');
    adminOverrides.addMethod('GET', lambdaIntegration, {
      authorizer: authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });
    adminOverrides.addMethod('POST', lambdaIntegration, {
      authorizer: authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    const overrideGuid = adminOverrides.addResource('{guid}');
    overrideGuid.addMethod('DELETE', lambdaIntegration, {
      authorizer: authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    this.apiEndpoint = api.url;

    // Setup custom domain if hosted zone is available
    if (stackConfig.features.enableCustomDomain && stackConfig.hostedZoneId) {
      const hostedZone = route53.HostedZone.fromHostedZoneAttributes(
        this,
        'ApiHostedZone',
        {
          hostedZoneId: stackConfig.hostedZoneId,
          zoneName: baseDomain,
        }
      );

      // Create ACM certificate for API domain
      const certificate = new acm.Certificate(this, 'ApiCertificate', {
        domainName: apiDomain,
        validation: acm.CertificateValidation.fromDns(hostedZone),
      });

      // Create custom domain name (REGIONAL for use with CloudFront)
      // Changed logical ID from 'ApiCustomDomain' to force replacement from EDGE to REGIONAL
      this.customDomainName = new apigateway.DomainName(this, 'ApiCustomDomainRegional', {
        domainName: apiDomain,
        certificate: certificate,
        endpointType: apigateway.EndpointType.REGIONAL,
        securityPolicy: apigateway.SecurityPolicy.TLS_1_2,
      });

      // Create base path mapping
      new apigateway.BasePathMapping(this, 'ApiBasePathMapping', {
        domainName: this.customDomainName,
        restApi: api,
        stage: api.deploymentStage,
      });

      // Create CloudFront distribution for caching
      const distribution = new cloudfront.Distribution(this, 'ApiDistribution', {
        comment: 'CloudFront distribution for next.dctech.events API',
        domainNames: [apiDomain],
        certificate: certificate,
        defaultBehavior: {
          origin: new origins.RestApiOrigin(api),
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
          cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
          compress: true,
          // Default behavior: no caching for authenticated endpoints
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER,
        },
        additionalBehaviors: {
          // Cache /api/events* (public event list)
          '/api/events*': {
            origin: new origins.RestApiOrigin(api),
            viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
            cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
            compress: true,
            cachePolicy: new cloudfront.CachePolicy(this, 'EventsCachePolicy', {
              cachePolicyName: 'DctechEventsApiEventsCache',
              comment: 'Cache policy for /api/events endpoints (1 hour TTL)',
              defaultTtl: cdk.Duration.hours(1),
              minTtl: cdk.Duration.seconds(0),
              maxTtl: cdk.Duration.hours(24),
              enableAcceptEncodingGzip: true,
              enableAcceptEncodingBrotli: true,
              queryStringBehavior: cloudfront.CacheQueryStringBehavior.all(),
            }),
          },
          // Cache /api/overrides (public overrides)
          '/api/overrides': {
            origin: new origins.RestApiOrigin(api),
            viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
            cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
            compress: true,
            cachePolicy: new cloudfront.CachePolicy(this, 'OverridesCachePolicy', {
              cachePolicyName: 'DctechEventsApiOverridesCache',
              comment: 'Cache policy for /api/overrides endpoint (1 hour TTL)',
              defaultTtl: cdk.Duration.hours(1),
              minTtl: cdk.Duration.seconds(0),
              maxTtl: cdk.Duration.hours(24),
              enableAcceptEncodingGzip: true,
              enableAcceptEncodingBrotli: true,
              queryStringBehavior: cloudfront.CacheQueryStringBehavior.all(),
            }),
          },
        },
        httpVersion: cloudfront.HttpVersion.HTTP2_AND_3,
        minimumProtocolVersion: cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
        priceClass: cloudfront.PriceClass.PRICE_CLASS_100, // North America and Europe
      });

      // Create Route53 A record (IPv4) pointing to CloudFront
      new route53.ARecord(this, 'ApiARecord', {
        zone: hostedZone,
        recordName: apiDomain,
        target: route53.RecordTarget.fromAlias(
          new route53targets.CloudFrontTarget(distribution)
        ),
        comment: 'IPv4 record for next.dctech.events API (via CloudFront)',
      });

      // Create Route53 AAAA record (IPv6) pointing to CloudFront
      new route53.AaaaRecord(this, 'ApiAAAARecord', {
        zone: hostedZone,
        recordName: apiDomain,
        target: route53.RecordTarget.fromAlias(
          new route53targets.CloudFrontTarget(distribution)
        ),
        comment: 'IPv6 record for next.dctech.events API (via CloudFront)',
      });

      // Output custom domain info
      new cdk.CfnOutput(this, 'CustomDomainName', {
        value: apiDomain,
        description: 'Custom domain name for API',
        exportName: 'DctechEventsApiCustomDomain',
      });

      new cdk.CfnOutput(this, 'CustomDomainUrl', {
        value: `https://${apiDomain}`,
        description: 'Custom domain URL for API',
        exportName: 'DctechEventsApiCustomDomainUrl',
      });

      new cdk.CfnOutput(this, 'CloudFrontDistributionId', {
        value: distribution.distributionId,
        description: 'CloudFront distribution ID',
        exportName: 'DctechEventsApiDistributionId',
      });

      new cdk.CfnOutput(this, 'CloudFrontDomainName', {
        value: distribution.distributionDomainName,
        description: 'CloudFront distribution domain name',
        exportName: 'DctechEventsApiDistributionDomain',
      });
    }

    // Stack outputs
    new cdk.CfnOutput(this, 'ApiEndpoint', {
      value: this.apiEndpoint,
      description: 'API Gateway endpoint URL',
      exportName: 'DctechEventsApiEndpoint',
    });

    new cdk.CfnOutput(this, 'FunctionArn', {
      value: this.apiFunction.functionArn,
      description: 'Lambda function ARN',
      exportName: 'DctechEventsApiFunctionArn',
    });

    // Apply tags
    cdk.Tags.of(this).add('project', 'dctech-events');
    cdk.Tags.of(this).add('component', 'api');
    cdk.Tags.of(this).add('managedBy', 'CDK');
  }
}
