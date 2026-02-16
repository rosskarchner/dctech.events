import * as cdk from 'aws-cdk-lib/core';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { Construct } from 'constructs';

export interface DynamoDBStackProps extends cdk.StackProps {
  /**
   * Name of the DynamoDB table
   * @default 'dctech-events'
   */
  tableName?: string;

  /**
   * Removal policy for the DynamoDB table
   * @default cdk.RemovalPolicy.RETAIN (production-safe)
   */
  removalPolicy?: cdk.RemovalPolicy;
}

/**
 * DynamoDB Stack for DC Tech Events
 *
 * Single-table design with the following entities:
 * - Event: Imported from iCal feeds or user-submitted
 * - Group: Tech meetup groups with calendar feeds
 * - Category: Event categories (AI, Cybersecurity, etc.)
 * - Draft: Pending user submissions for moderation
 * - User: Cognito users with submission history
 * - ICalCache: Cached iCal feed data
 * - ICalMeta: Metadata for iCal imports
 *
 * Access Patterns:
 * - Get event by GUID (PK: EVENT#{guid}, SK: META)
 * - List events by date (GSI1: PK=DATE#{date}, SK=TIME#{time})
 * - Get group by slug (PK: GROUP#{slug}, SK: META)
 * - List active groups (GSI1: PK=ACTIVE#1, SK=NAME#{name})
 * - List drafts by status (GSI1: PK=STATUS#{status}, SK={created_at})
 * - Get user by Cognito sub (PK: USER#{sub}, SK: META)
 * - Query user submissions (GSI3: PK={submitter_id}, SK={created_at})
 * - Query events by category (GSI2: PK=CATEGORY#{slug}, SK=DATE#{date})
 * - Get cached iCal events (PK: ICAL#{group_id}, SK: EVENT#{guid})
 */
export class DynamoDBStack extends cdk.Stack {
  public readonly table: dynamodb.Table;

  constructor(scope: Construct, id: string, props?: DynamoDBStackProps) {
    super(scope, id, props);

    const tableName = props?.tableName || 'dctech-events';
    const removalPolicy = props?.removalPolicy || cdk.RemovalPolicy.RETAIN;

    // Create DynamoDB table with single-table design
    this.table = new dynamodb.Table(this, 'DctechEventsTable', {
      tableName: tableName,

      // Partition key (PK) and Sort key (SK) for main table
      partitionKey: {
        name: 'PK',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'SK',
        type: dynamodb.AttributeType.STRING,
      },

      // Billing mode
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,

      // Enable point-in-time recovery for production safety
      pointInTimeRecovery: true,

      // Removal policy (RETAIN for production, DESTROY for dev/test)
      removalPolicy: removalPolicy,

      // Enable deletion protection in production
      deletionProtection: removalPolicy === cdk.RemovalPolicy.RETAIN,

      // Enable encryption at rest
      encryption: dynamodb.TableEncryption.AWS_MANAGED,

      // Enable TTL for cached iCal data
      timeToLiveAttribute: 'ttl',

      // Enable DynamoDB Streams for rebuild triggers
      stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
    });

    // GSI1: Query events by date, drafts by status, active groups
    this.table.addGlobalSecondaryIndex({
      indexName: 'GSI1',
      partitionKey: {
        name: 'GSI1PK',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'GSI1SK',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // GSI2: Query events/groups by category
    this.table.addGlobalSecondaryIndex({
      indexName: 'GSI2',
      partitionKey: {
        name: 'GSI2PK',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'GSI2SK',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // GSI3: Query user's submissions
    this.table.addGlobalSecondaryIndex({
      indexName: 'GSI3',
      partitionKey: {
        name: 'GSI3PK',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'GSI3SK',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // Stack outputs
    new cdk.CfnOutput(this, 'TableName', {
      value: this.table.tableName,
      description: 'DynamoDB table name',
      exportName: 'DctechEventsTableName',
    });

    new cdk.CfnOutput(this, 'TableArn', {
      value: this.table.tableArn,
      description: 'DynamoDB table ARN',
      exportName: 'DctechEventsTableArn',
    });

    new cdk.CfnOutput(this, 'TableStreamArn', {
      value: this.table.tableStreamArn!,
      description: 'DynamoDB table stream ARN',
      exportName: 'DctechEventsTableStreamArn',
    });

    // Apply tags
    cdk.Tags.of(this).add('project', 'dctech-events');
    cdk.Tags.of(this).add('component', 'database');
    cdk.Tags.of(this).add('managedBy', 'CDK');
  }
}
