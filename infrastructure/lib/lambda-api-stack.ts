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
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import { Construct } from 'constructs';
import { LambdaApiStackProps } from './interfaces';
import { stackConfig } from './config';
import * as path from 'path';
import { execSync } from 'child_process';

/**
 * Lambda API Stack for DC Tech Events
 *
 * Deploys the Python application as a Lambda function with API Gateway REST API.
 * Handles event submissions and moderation.
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
    lambdaRole.addToPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['dynamodb:Query', 'dynamodb:GetItem', 'dynamodb:Scan'],
      resources: [props.materializedTableArn, `${props.materializedTableArn}/index/*`],
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
      runtime: lambda.Runtime.PYTHON_3_12,
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

    // 4. Queue Notification Lambda (Daily 8:30 AM EST)
    const queueNotificationFn = new lambda.Function(this, 'QueueNotificationFunction', {
      functionName: 'dctech-events-queue-notification',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'queue_notification/handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../..'), {
        exclude: ['.git', 'node_modules', '.beads', '.venv', 'infrastructure', 'build', 'static', '_cache', '_data', '__pycache__'],
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install requests pytz pyyaml -t /asset-output && cp -r lambdas/* /asset-output/ && cp config.yaml /asset-output/ && cp db_utils.py /asset-output/',
          ],
        },
      }),
      timeout: cdk.Duration.seconds(30),
      architecture: lambda.Architecture.ARM_64,
      environment: {
        CONFIG_TABLE_NAME: props.dynamoStack.table.tableName,
        ADMIN_EMAIL: stackConfig.notifications.adminEmail,
      },
      logGroup: new logs.LogGroup(this, 'QueueNotificationLogGroup', {
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }),
    });

    // Grant permissions for Queue Notification
    queueNotificationFn.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['dynamodb:Query'],
      resources: [props.dynamoStack.table.tableArn, `${props.dynamoStack.table.tableArn}/index/GSI1`],
    }));

    queueNotificationFn.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['ses:SendEmail', 'ses:SendRawEmail'],
      resources: ['*'],
    }));

    // Trigger daily submission queue email notification (Daily 8:30 AM EST = 13:30 UTC)
    new events.Rule(this, 'QueueNotificationScheduleRule', {
      schedule: events.Schedule.expression('cron(30 13 * * ? *)'),
      targets: [new targets.LambdaFunction(queueNotificationFn)],
      description: 'Trigger daily submission queue email notification (Daily 8:30 AM EST)',
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

    // Create an unmanaged version of the function for API Gateway
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
    const health = api.root.addResource('health');
    health.addMethod('GET', lambdaIntegration);

    const apiResource = api.root.addResource('api');
    const eventsResource = apiResource.addResource('events');
    eventsResource.addMethod('GET', lambdaIntegration); // Public API

    const upcomingIcs = eventsResource.addResource('upcoming.ics');
    upcomingIcs.addMethod('GET', lambdaIntegration);

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

    this.apiFunction.addPermission('ApiGatewayInvokeAll', {
      principal: new iam.ServicePrincipal('apigateway.amazonaws.com'),
      action: 'lambda:InvokeFunction',
      sourceArn: api.arnForExecuteApi('*', '/*', stageName),
    });

    this.apiEndpoint = api.url;

    // Add usage plan
    const usagePlan = api.addUsagePlan('ApiUsagePlan', {
      name: 'dctech-events-api-usage-plan',
      throttle: {
        rateLimit: 100,
        burstLimit: 200,
      },
      quota: {
        limit: 10000,
        period: apigateway.Period.DAY,
      },
    });

    usagePlan.addApiStage({
      stage: api.deploymentStage,
    });

    // Setup custom domain
    if (stackConfig.features.enableCustomDomain && stackConfig.hostedZoneId) {
      const hostedZone = route53.HostedZone.fromHostedZoneAttributes(
        this,
        'ApiHostedZone',
        {
          hostedZoneId: stackConfig.hostedZoneId,
          zoneName: baseDomain,
        }
      );

      const certificate = new acm.Certificate(this, 'ApiCertificate', {
        domainName: apiDomain,
        subjectAlternativeNames: ['manage.dctech.events', 'suggest.dctech.events'],
        validation: acm.CertificateValidation.fromDns(hostedZone),
      });

      const oac = new cloudfront.S3OriginAccessControl(this, 'EditFrontendOAC', {
        description: 'OAC for DC Tech Events edit frontend bucket',
      });

      const directoryIndexFunction = new cloudfront.Function(this, 'DirectoryIndexFunction', {
        code: cloudfront.FunctionCode.fromInline(`
function handler(event) {
  var request = event.request;
  var headers = request.headers;
  var host = headers.host ? headers.host.value : '';

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
        functionName: 'dctech-events-edit-directory-index',
      });

      this.customDomainName = new apigateway.DomainName(this, 'ApiCustomDomainRegional', {
        domainName: apiDomain,
        certificate: certificate,
        endpointType: apigateway.EndpointType.REGIONAL,
        securityPolicy: apigateway.SecurityPolicy.TLS_1_2,
      });

      new apigateway.BasePathMapping(this, 'ApiBasePathMapping', {
        domainName: this.customDomainName,
        restApi: api,
        stage: api.deploymentStage,
      });

      const corsResponseHeadersPolicy = new cloudfront.ResponseHeadersPolicy(this, 'ApiCorsResponseHeaders', {
        responseHeadersPolicyName: 'DctechEventsEditCors',
        corsBehavior: {
          accessControlAllowOrigins: ['https://edit.dctech.events', 'https://dctech.events', 'https://manage.dctech.events', 'https://suggest.dctech.events'],
          accessControlAllowMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
          accessControlAllowHeaders: ['Content-Type', 'Authorization', 'HX-Request', 'HX-Trigger', 'HX-Trigger-Name', 'HX-Target', 'HX-Current-URL'],
          accessControlAllowCredentials: false,
          originOverride: false,
        },
      });

      const distribution = new cloudfront.Distribution(this, 'ApiDistribution', {
        domainNames: [apiDomain, 'manage.dctech.events', 'suggest.dctech.events'],
        certificate: certificate,
        defaultRootObject: 'index.html',
        defaultBehavior: {
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
          '/api/events*': {
            origin: new origins.RestApiOrigin(api),
            viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
            cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
            compress: true,
            responseHeadersPolicy: corsResponseHeadersPolicy,
            cachePolicy: new cloudfront.CachePolicy(this, 'EventsCachePolicy', {
              cachePolicyName: 'DctechEventsEditApiEventsCache',
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
      });

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

      const domains = [apiDomain, 'manage.dctech.events', 'suggest.dctech.events'];
      for (const domain of domains) {
        const subdomain = domain.split('.')[0];
        const idPrefix = subdomain === 'edit' ? '' : subdomain.charAt(0).toUpperCase() + subdomain.slice(1);
        
        new route53.ARecord(this, `ApiARecord${idPrefix}`, {
          zone: hostedZone,
          recordName: domain,
          target: route53.RecordTarget.fromAlias(
            new route53targets.CloudFrontTarget(distribution)
          ),
        });

        new route53.AaaaRecord(this, `ApiAAAARecord${idPrefix}`, {
          zone: hostedZone,
          recordName: domain,
          target: route53.RecordTarget.fromAlias(
            new route53targets.CloudFrontTarget(distribution)
          ),
        });
      }
    }

    // Stack outputs
    new cdk.CfnOutput(this, 'ApiEndpoint', {
      value: this.apiEndpoint,
      exportName: 'DctechEventsApiEndpoint',
    });

    new cdk.CfnOutput(this, 'FunctionArn', {
      value: this.apiFunction.functionArn,
      exportName: 'DctechEventsApiFunctionArn',
    });

    cdk.Tags.of(this).add('project', 'dctech-events');
    cdk.Tags.of(this).add('component', 'api');
    cdk.Tags.of(this).add('managedBy', 'CDK');
  }
}
