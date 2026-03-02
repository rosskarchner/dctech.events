import * as cdk from 'aws-cdk-lib/core';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as route53targets from 'aws-cdk-lib/aws-route53-targets';
import * as s3 from 'aws-cdk-lib/aws-s3';
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
    const apiDomain = 'edit.dctech.events';
    const baseDomain = 'dctech.events';

    // S3 Bucket for unified Edit frontend
    const editBucket = new s3.Bucket(this, 'EditFrontendBucket', {
      bucketName: 'dctech-events-edit-frontend',
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: false,
      encryption: s3.BucketEncryption.S3_MANAGED,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

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

    // Add read access to DcTechEvents materialized table
    const materializedTableName = stackConfig.dynamodb.tableName;
    const materializedTableArn = `arn:aws:dynamodb:${cdk.Stack.of(this).region}:${cdk.Stack.of(this).account}:table/${materializedTableName}`;
    lambdaRole.addToPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['dynamodb:Query', 'dynamodb:GetItem', 'dynamodb:Scan'],
      resources: [materializedTableArn, `${materializedTableArn}/index/*`],
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
      code: lambda.Code.fromAsset(path.join(__dirname, '../..'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -r backend/requirements.txt -t /asset-output && cp -au backend/. /asset-output && cp dynamo_data.py versioned_db.py /asset-output/',
          ],
          local: {
            tryBundle(outputDir: string) {
              try {
                execSync('python3 -m pip --version');
              } catch {
                return false;
              }

              const root = path.join(__dirname, '../..');
              const commands = [
                `python3 -m pip install -r ${root}/backend/requirements.txt -t ${outputDir} --platform manylinux2014_aarch64 --implementation cp --python-version 3.12 --only-binary=:all: --upgrade`,
                `cp -r ${root}/backend/* ${outputDir}`,
                `cp ${root}/dynamo_data.py ${outputDir}/`,
                `cp ${root}/versioned_db.py ${outputDir}/`,
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
          '.beads',
          'infrastructure',
          'build',
          'frontends',
          'migrations',
        ],
      }),
      role: lambdaRole,
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      architecture: lambda.Architecture.ARM_64,
      environment: {
        COGNITO_USER_POOL_ID: props.cognitoStack.userPool.userPoolId,
        COGNITO_USER_POOL_CLIENT_ID: props.cognitoStack.userPoolClient.userPoolClientId,
        COGNITO_DOMAIN: cognitoDomain,
        COGNITO_CLIENT_SECRET_NAME: stackConfig.secrets.cognitoClientSecret,
        DYNAMODB_TABLE_NAME: props.dynamoStack.table.tableName,
        MATERIALIZED_TABLE_NAME: stackConfig.dynamodb.tableName,
        STAGE: stageName,
      },
      logGroup: new logs.LogGroup(this, 'ApiFunctionLogGroup', {
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }),
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
        allowHeaders: ['Content-Type', 'Authorization', 'HX-Request', 'HX-Trigger', 'HX-Trigger-Name', 'HX-Target', 'HX-Current-URL'],
      },
    });

    // Create Cognito User Pool Authorizer
    const authorizer = new apigateway.CognitoUserPoolsAuthorizer(this, 'CognitoAuthorizer', {
      cognitoUserPools: [props.cognitoStack.userPool],
      identitySource: 'method.request.header.Authorization',
    });

    // Create an unmanaged version of the function for API Gateway to avoid CDK adding 
    // individual permissions for every single route, which hits the 20KB policy limit.
    // We already add a blanket permission below.
    const unmanagedApiFunction = lambda.Function.fromFunctionArn(
      this, 
      'UnmanagedApiFunction', 
      this.apiFunction.functionArn
    );

    // Create Lambda integration
    const lambdaIntegration = new apigateway.LambdaIntegration(unmanagedApiFunction, {
      proxy: true,
      allowTestInvoke: false,
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

    const mySubmissions = api.root.addResource('my-submissions');
    mySubmissions.addMethod('GET', lambdaIntegration, {
      authorizer: authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    // Admin routes — use {proxy+} to avoid Lambda policy size limit from per-method permissions
    const admin = api.root.addResource('admin');
    admin.addMethod('ANY', lambdaIntegration, {
      authorizer: authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });
    const adminProxy = admin.addProxy({
      defaultIntegration: lambdaIntegration,
      defaultMethodOptions: {
        authorizer: authorizer,
        authorizationType: apigateway.AuthorizationType.COGNITO,
      },
      anyMethod: true,
    });

    // Explicit wildcard Lambda invoke permission covering all routes.
    // LambdaIntegration auto-generates per-route permissions, but they can drift out of sync
    // (e.g. if CF state gets corrupted). This blanket permission ensures all routes always work.
    this.apiFunction.addPermission('ApiGatewayInvokeAll', {
      principal: new iam.ServicePrincipal('apigateway.amazonaws.com'),
      action: 'lambda:InvokeFunction',
      sourceArn: api.arnForExecuteApi('*', '/*', stageName),
    });

    this.apiEndpoint = api.url;

    // Add usage plan with rate limiting and throttling
    const usagePlan = api.addUsagePlan('ApiUsagePlan', {
      name: 'dctech-events-api-usage-plan',
      description: 'Rate limiting for DC Tech Events API',
      throttle: {
        rateLimit: 100,    // Requests per second
        burstLimit: 200,   // Maximum concurrent requests
      },
      quota: {
        limit: 10000,      // Total requests per day
        period: apigateway.Period.DAY,
      },
    });

    // Associate usage plan with the API stage
    usagePlan.addApiStage({
      stage: api.deploymentStage,
    });

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
        subjectAlternativeNames: ['manage.dctech.events', 'suggest.dctech.events'],
        validation: acm.CertificateValidation.fromDns(hostedZone),
      });

      // Origin Access Control for CloudFront to access S3
      const oac = new cloudfront.S3OriginAccessControl(this, 'EditFrontendOAC', {
        description: 'OAC for DC Tech Events edit frontend bucket',
      });

      // CloudFront Function to rewrite directory URLs to index.html and handle legacy redirects
      const directoryIndexFunction = new cloudfront.Function(this, 'DirectoryIndexFunction', {
        code: cloudfront.FunctionCode.fromInline(`
function handler(event) {
  var request = event.request;
  var headers = request.headers;
  var host = headers.host ? headers.host.value : '';

  // Redirect legacy subdomains to edit.dctech.events
  if (host === 'manage.dctech.events' || host === 'suggest.dctech.events') {
    return {
      statusCode: 301,
      statusDescription: 'Moved Permanently',
      headers: {
        'location': { 'value': 'https://edit.dctech.events' + request.uri }
      }
    };
  }

  var uri = request.uri;
  if (uri.endsWith('/')) {
    request.uri += 'index.html';
  } else if (!uri.includes('.')) {
    request.uri += '/index.html';
  }

  return request;
}
        `),
        comment: 'Rewrite directory URLs and handle legacy redirects',
        functionName: 'dctech-events-edit-directory-index',
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

      // Create CloudFront distribution for caching and serving static files
      // CORS response headers policy for API
      const corsResponseHeadersPolicy = new cloudfront.ResponseHeadersPolicy(this, 'ApiCorsResponseHeaders', {
        responseHeadersPolicyName: 'DctechEventsEditCors',
        comment: 'CORS headers for edit.dctech.events API',
        corsBehavior: {
          accessControlAllowOrigins: ['https://edit.dctech.events', 'https://dctech.events', 'https://manage.dctech.events', 'https://suggest.dctech.events'],
          accessControlAllowMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
          accessControlAllowHeaders: ['Content-Type', 'Authorization', 'HX-Request', 'HX-Trigger', 'HX-Trigger-Name', 'HX-Target', 'HX-Current-URL'],
          accessControlAllowCredentials: false,
          originOverride: false,
        },
      });

      const distribution = new cloudfront.Distribution(this, 'ApiDistribution', {
        comment: 'CloudFront distribution for edit.dctech.events (API + Frontend)',
        domainNames: [apiDomain, 'manage.dctech.events', 'suggest.dctech.events'],
        certificate: certificate,
        defaultRootObject: 'index.html',
        defaultBehavior: {
          // Default behavior serves static files from S3
          origin: origins.S3BucketOrigin.withOriginAccessControl(editBucket, {
            originAccessControl: oac,
          }),
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          compress: true,
          cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
          functionAssociations: [
            {
              function: directoryIndexFunction,
              eventType: cloudfront.FunctionEventType.VIEWER_REQUEST,
            },
          ],
        },
        additionalBehaviors: {
          // API routes point to API Gateway
          '/api/*': {
            origin: new origins.RestApiOrigin(api),
            viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
            cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
            compress: true,
            cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
            originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
            responseHeadersPolicy: corsResponseHeadersPolicy,
          },
          '/admin/*': {
            origin: new origins.RestApiOrigin(api),
            viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
            cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
            compress: true,
            cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
            originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
            responseHeadersPolicy: corsResponseHeadersPolicy,
          },
          '/admin': {
            origin: new origins.RestApiOrigin(api),
            viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
            cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
            compress: true,
            cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
            originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
            responseHeadersPolicy: corsResponseHeadersPolicy,
          },
          '/submit': {
            origin: new origins.RestApiOrigin(api),
            viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
            cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
            compress: true,
            cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
            originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
            responseHeadersPolicy: corsResponseHeadersPolicy,
          },
          '/my-submissions': {
            origin: new origins.RestApiOrigin(api),
            viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
            cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
            compress: true,
            cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
            originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
            responseHeadersPolicy: corsResponseHeadersPolicy,
          },
          '/health': {
            origin: new origins.RestApiOrigin(api),
            viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
            cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
            compress: true,
            cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
            responseHeadersPolicy: corsResponseHeadersPolicy,
          },
          // Cache /api/events* (public event list)
          '/api/events*': {
            origin: new origins.RestApiOrigin(api),
            viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
            cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
            compress: true,
            responseHeadersPolicy: corsResponseHeadersPolicy,
            cachePolicy: new cloudfront.CachePolicy(this, 'EventsCachePolicy', {
              cachePolicyName: 'DctechEventsEditApiEventsCache',
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
            responseHeadersPolicy: corsResponseHeadersPolicy,
            cachePolicy: new cloudfront.CachePolicy(this, 'OverridesCachePolicy', {
              cachePolicyName: 'DctechEventsEditApiOverridesCache',
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
        priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
        errorResponses: [
          {
            httpStatus: 403,
            responseHttpStatus: 200,
            responsePagePath: '/index.html',
            ttl: cdk.Duration.minutes(5),
          },
          {
            httpStatus: 404,
            responseHttpStatus: 200,
            responsePagePath: '/index.html',
            ttl: cdk.Duration.minutes(5),
          },
        ],
      });

      // Bucket policy for CloudFront OAC access
      editBucket.addToResourcePolicy(
        new iam.PolicyStatement({
          actions: ['s3:GetObject'],
          resources: [editBucket.arnForObjects('*')],
          principals: [new iam.ServicePrincipal('cloudfront.amazonaws.com')],
          conditions: {
            StringEquals: {
              'AWS:SourceArn': `arn:aws:cloudfront::${cdk.Stack.of(this).account}:distribution/${distribution.distributionId}`,
            },
          },
        })
      );

      // Create Route53 A and AAAA records pointing to CloudFront for all domains
      const domains = [apiDomain, 'manage.dctech.events', 'suggest.dctech.events'];
      for (const domain of domains) {
        const subdomain = domain.split('.')[0];
        // Reuse original logical IDs for 'edit' to avoid duplicate resource errors
        const idPrefix = subdomain === 'edit' ? '' : subdomain.charAt(0).toUpperCase() + subdomain.slice(1);
        
        new route53.ARecord(this, `ApiARecord${idPrefix}`, {
          zone: hostedZone,
          recordName: domain,
          target: route53.RecordTarget.fromAlias(
            new route53targets.CloudFrontTarget(distribution)
          ),
          comment: `IPv4 record for ${domain} (Consolidated via CloudFront)`,
        });

        new route53.AaaaRecord(this, `ApiAAAARecord${idPrefix}`, {
          zone: hostedZone,
          recordName: domain,
          target: route53.RecordTarget.fromAlias(
            new route53targets.CloudFrontTarget(distribution)
          ),
          comment: `IPv6 record for ${domain} (Consolidated via CloudFront)`,
        });
      }

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
