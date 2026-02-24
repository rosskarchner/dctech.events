import * as cdk from 'aws-cdk-lib/core';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as eventsources from 'aws-cdk-lib/aws-lambda-event-sources';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import { Construct } from 'constructs';
import { DynamoDBStack } from './dynamodb-stack';
import { stackConfig } from './config';
import * as path from 'path';

export interface RebuildStackProps extends cdk.StackProps {
  /**
   * Reference to the DynamoDB config table stack (for stream ARN)
   */
  dynamoStack: DynamoDBStack;

  /**
   * S3 bucket name for the static site
   */
  siteBucketName?: string;

  /**
   * S3 bucket name for the data cache
   */
  dataCacheBucketName?: string;

  /**
   * CloudFront distribution ID for invalidation
   */
  cloudFrontDistributionId?: string;

  /**
   * DynamoDB materialized view table name (DcTechEvents)
   */
  materializedTableName?: string;
}

/**
 * Rebuild Pipeline Stack
 *
 * Architecture: DynamoDB Streams → dispatcher Lambda → SQS FIFO (dedup) → rebuild worker Lambda
 *
 * The dispatcher Lambda receives DynamoDB stream events from the config table
 * and sends a message to the SQS FIFO queue with content-based deduplication
 * (floor(epoch/60) as dedup ID) to batch rapid changes into a single rebuild.
 *
 * The rebuild worker Lambda (Docker image) runs the static site build:
 * 1. npm run build (JS assets)
 * 2. freeze.py (static site generation from DynamoDB)
 * 3. Sync build/ to S3
 * 4. CloudFront invalidation
 *
 * iCal refresh runs separately on a schedule (EventBridge → ical-refresh Lambda)
 * and writes events directly to the config table. Config table changes then
 * trigger the rebuild pipeline via DynamoDB Streams.
 */
export class RebuildStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: RebuildStackProps) {
    super(scope, id, props);

    const siteBucketName = props.siteBucketName || stackConfig.s3.bucketName;
    const dataCacheBucketName = props.dataCacheBucketName || stackConfig.s3.dataCacheBucketName;
    const materializedTableName = props.materializedTableName || stackConfig.dynamodb.tableName;

    // SQS FIFO queue with content-based deduplication
    const rebuildQueue = new sqs.Queue(this, 'RebuildQueue', {
      queueName: stackConfig.rebuild.queueName,
      fifo: true,
      contentBasedDeduplication: false, // We set explicit dedup IDs
      visibilityTimeout: cdk.Duration.seconds(stackConfig.rebuild.visibilityTimeoutSeconds),
      retentionPeriod: cdk.Duration.hours(4),
      deadLetterQueue: {
        queue: new sqs.Queue(this, 'RebuildDLQ', {
          queueName: 'dctech-events-rebuild-dlq.fifo',
          fifo: true,
          retentionPeriod: cdk.Duration.days(7),
        }),
        maxReceiveCount: 3,
      },
    });

    // Stream dispatcher Lambda
    const dispatcherFn = new lambda.Function(this, 'StreamDispatcher', {
      functionName: 'dctech-events-stream-dispatcher',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/stream_dispatcher')),
      timeout: cdk.Duration.seconds(30),
      memorySize: 128,
      environment: {
        REBUILD_QUEUE_URL: rebuildQueue.queueUrl,
        DEDUP_WINDOW_SECONDS: String(stackConfig.rebuild.deduplicationWindowSeconds),
      },
      logGroup: new logs.LogGroup(this, 'StreamDispatcherLogGroup', {
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }),
    });

    // Grant dispatcher permission to send messages to queue
    rebuildQueue.grantSendMessages(dispatcherFn);

    // Connect dispatcher to DynamoDB stream
    dispatcherFn.addEventSource(new eventsources.DynamoEventSource(props.dynamoStack.table, {
      startingPosition: lambda.StartingPosition.TRIM_HORIZON,
      batchSize: 10,
      maxBatchingWindow: cdk.Duration.seconds(5),
      retryAttempts: 3,
      bisectBatchOnError: true,
      reportBatchItemFailures: true,
    }));

    // Rebuild worker Lambda (Docker image)
    // Build context is repo root so Dockerfile can COPY the full project
    const rebuildWorkerFn = new lambda.DockerImageFunction(this, 'RebuildWorker', {
      functionName: 'dctech-events-rebuild-worker',
      code: lambda.DockerImageCode.fromImageAsset(
        path.join(__dirname, '../..'),  // repo root as build context
        { file: 'lambdas/rebuild_worker/Dockerfile' }
      ),
      timeout: cdk.Duration.seconds(stackConfig.rebuild.lambdaTimeoutSeconds),
      memorySize: stackConfig.rebuild.lambdaMemoryMB,
      environment: {
        SITE_BUCKET: siteBucketName,
        DATA_CACHE_BUCKET: dataCacheBucketName,
        MATERIALIZED_TABLE_NAME: materializedTableName,
        CONFIG_TABLE_NAME: 'dctech-events',
        CLOUDFRONT_DISTRIBUTION_ID: props.cloudFrontDistributionId || '',
      },
      logGroup: new logs.LogGroup(this, 'RebuildWorkerLogGroup', {
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }),
    });

    // Connect rebuild worker to SQS queue
    rebuildWorkerFn.addEventSource(new eventsources.SqsEventSource(rebuildQueue, {
      batchSize: 1,
    }));

    // Grant rebuild worker permissions
    // S3 access for both buckets
    rebuildWorkerFn.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['s3:GetObject', 's3:PutObject', 's3:DeleteObject', 's3:ListBucket'],
      resources: [
        `arn:aws:s3:::${siteBucketName}`,
        `arn:aws:s3:::${siteBucketName}/*`,
        `arn:aws:s3:::${dataCacheBucketName}`,
        `arn:aws:s3:::${dataCacheBucketName}/*`,
      ],
    }));

    // DynamoDB access for both tables
    rebuildWorkerFn.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'dynamodb:GetItem', 'dynamodb:PutItem', 'dynamodb:UpdateItem',
        'dynamodb:DeleteItem', 'dynamodb:Query', 'dynamodb:Scan',
        'dynamodb:BatchGetItem', 'dynamodb:BatchWriteItem',
      ],
      resources: [
        props.dynamoStack.table.tableArn,
        `${props.dynamoStack.table.tableArn}/index/*`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/${materializedTableName}`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/${materializedTableName}/index/*`,
      ],
    }));

    // CloudFront invalidation permission
    rebuildWorkerFn.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['cloudfront:CreateInvalidation'],
      resources: ['*'],
    }));

    // iCal Refresh Lambda (runs on schedule, writes events to config table)
    const icalRefreshFn = new lambda.DockerImageFunction(this, 'IcalRefreshWorker', {
      functionName: 'dctech-events-ical-refresh',
      code: lambda.DockerImageCode.fromImageAsset(
        path.join(__dirname, '../..'),  // repo root as build context
        { file: 'lambdas/rebuild_worker/Dockerfile' }
      ),
      timeout: cdk.Duration.seconds(600),
      memorySize: 1024,
      environment: {
        CONFIG_TABLE_NAME: 'dctech-events',
        ICAL_REFRESH_MODE: 'true',  // Tells handler to run refresh only
      },
      logGroup: new logs.LogGroup(this, 'IcalRefreshLogGroup', {
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }),
    });

    // Grant iCal refresh Lambda access to config table
    icalRefreshFn.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'dynamodb:GetItem', 'dynamodb:PutItem', 'dynamodb:UpdateItem',
        'dynamodb:Query', 'dynamodb:Scan',
      ],
      resources: [
        props.dynamoStack.table.tableArn,
        `${props.dynamoStack.table.tableArn}/index/*`,
      ],
    }));

    // Schedule iCal refresh every 4 hours
    new events.Rule(this, 'IcalRefreshSchedule', {
      ruleName: 'dctech-events-ical-refresh-schedule',
      schedule: events.Schedule.rate(cdk.Duration.hours(4)),
      targets: [new targets.LambdaFunction(icalRefreshFn)],
    });

    // Stack outputs
    new cdk.CfnOutput(this, 'QueueUrl', {
      value: rebuildQueue.queueUrl,
      description: 'Rebuild SQS FIFO queue URL',
    });

    new cdk.CfnOutput(this, 'DispatcherFunctionArn', {
      value: dispatcherFn.functionArn,
      description: 'Stream dispatcher Lambda ARN',
    });

    new cdk.CfnOutput(this, 'WorkerFunctionArn', {
      value: rebuildWorkerFn.functionArn,
      description: 'Rebuild worker Lambda ARN',
    });

    // Apply tags
    cdk.Tags.of(this).add('project', 'dctech-events');
    cdk.Tags.of(this).add('component', 'rebuild-pipeline');
    cdk.Tags.of(this).add('managedBy', 'CDK');
  }
}
