import * as cdk from 'aws-cdk-lib/core';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as iam from 'aws-cdk-lib/aws-iam';
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
  public readonly apiFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: LambdaApiStackProps) {
    super(scope, id, props);

    const stageName = props.stageName || stackConfig.chalice.mainApi.stageName;
    const cognitoDomain = props.cognitoDomain || stackConfig.cognito.domainPrefix;

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
      resources: [
        props.secretsStack.cognitoClientSecret.secretArn,
        props.secretsStack.githubTokenSecret.secretArn,
      ],
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
        GITHUB_TOKEN_SECRET_NAME: stackConfig.secrets.githubTokenSecret,
        GITHUB_REPO_OWNER: stackConfig.github.repositoryOwner,
        GITHUB_REPO_NAME: stackConfig.github.repositoryName,
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
    const authenticatedMethodOptions: apigateway.MethodOptions = {
      authorizer: authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
      authorizationScopes: ['openid'],
    };

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
    const categoriesResource = apiResource.addResource('categories');
    categoriesResource.addMethod('GET', lambdaIntegration); // Public API
    const apiSubmissions = apiResource.addResource('submissions');
    apiSubmissions.addMethod('POST', lambdaIntegration, authenticatedMethodOptions);
    const apiMySubmissions = apiResource.addResource('my-submissions');
    apiMySubmissions.addMethod('GET', lambdaIntegration, authenticatedMethodOptions);
    const apiAdmin = apiResource.addResource('admin');
    apiAdmin.addProxy({
      defaultIntegration: lambdaIntegration,
      defaultMethodOptions: authenticatedMethodOptions,
      anyMethod: true,
    });

    // Authenticated routes
    const submit = api.root.addResource('submit');
    submit.addMethod('GET', lambdaIntegration, authenticatedMethodOptions);
    submit.addMethod('POST', lambdaIntegration, authenticatedMethodOptions);

    const mySubmissions = api.root.addResource('my-submissions');
    mySubmissions.addMethod('GET', lambdaIntegration, authenticatedMethodOptions);

    const admin = api.root.addResource('admin');
    admin.addMethod('ANY', lambdaIntegration, authenticatedMethodOptions);
    const adminProxy = admin.addProxy({
      defaultIntegration: lambdaIntegration,
      defaultMethodOptions: authenticatedMethodOptions,
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
