import * as cdk from 'aws-cdk-lib/core';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import { DynamoDBStack } from './dynamodb-stack';
import { stackConfig } from './config';
import * as path from 'path';
import { execSync } from 'child_process';

/**
 * Stack properties for ImportEventsStack
 */
export interface ImportEventsStackProps extends cdk.StackProps {
  /**
   * Reference to the DynamoDBStack for table permissions
   */
  dynamoStack: DynamoDBStack;

  /**
   * GitHub repository in format "owner/repo"
   * @default 'rosskarchner/dctech.events'
   */
  githubRepo?: string;

  /**
   * GitHub branch to fetch from
   * @default 'main'
   */
  githubBranch?: string;
}

/**
 * Import Events Lambda Stack
 *
 * Deploys a Lambda function that imports single events from the GitHub
 * repository's _single_events directory into DynamoDB.
 *
 * The Lambda is idempotent - it uses deterministic GUIDs based on filenames,
 * so running it multiple times won't create duplicates.
 */
export class ImportEventsStack extends cdk.Stack {
  public readonly importFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: ImportEventsStackProps) {
    super(scope, id, props);

    const githubRepo = props.githubRepo || 'rosskarchner/dctech.events';
    const githubBranch = props.githubBranch || 'main';

    // Create Lambda execution role
    const lambdaRole = new iam.Role(this, 'ImportEventsLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: 'Execution role for import-single-events Lambda',
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Add DynamoDB permissions (read and write)
    lambdaRole.addToPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'dynamodb:GetItem',
        'dynamodb:PutItem',
        'dynamodb:UpdateItem',
        'dynamodb:Query',
        'dynamodb:Scan',
      ],
      resources: [
        props.dynamoStack.table.tableArn,
        `${props.dynamoStack.table.tableArn}/index/*`,
      ],
    }));

    // Create Lambda function
    this.importFunction = new lambda.Function(this, 'ImportSingleEventsFunction', {
      functionName: 'dctech-events-import-single-events',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'import_single_events.lambda_handler',
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
      timeout: cdk.Duration.minutes(5),  // GitHub fetching + DynamoDB writes
      memorySize: 512,
      environment: {
        DYNAMODB_TABLE_NAME: props.dynamoStack.table.tableName,
        GITHUB_REPO: githubRepo,
        GITHUB_BRANCH: githubBranch,
      },
      logGroup: new logs.LogGroup(this, 'ImportSingleEventsLogGroup', {
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }),
      description: 'Imports single events from GitHub _single_events directory to DynamoDB',
    });

    // Stack outputs
    new cdk.CfnOutput(this, 'ImportFunctionArn', {
      value: this.importFunction.functionArn,
      description: 'Lambda function ARN for importing single events',
      exportName: 'DctechEventsImportFunctionArn',
    });

    new cdk.CfnOutput(this, 'ImportFunctionName', {
      value: this.importFunction.functionName,
      description: 'Lambda function name',
      exportName: 'DctechEventsImportFunctionName',
    });

    // Apply tags
    cdk.Tags.of(this).add('project', 'dctech-events');
    cdk.Tags.of(this).add('component', 'import');
    cdk.Tags.of(this).add('managedBy', 'CDK');
  }
}
