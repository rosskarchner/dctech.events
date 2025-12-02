import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { InfrastructureStack } from '../lib/infrastructure-stack';

describe('InfrastructureStack', () => {
  let app: cdk.App;
  let stack: InfrastructureStack;
  let template: Template;

  beforeEach(() => {
    app = new cdk.App();
    // Create stack with a certificate ARN to avoid region validation error
    stack = new InfrastructureStack(app, 'TestStack', {
      env: { region: 'us-east-1', account: '123456789012' },
      certificateArn: 'arn:aws:acm:us-east-1:123456789012:certificate/test-cert-id',
    });
    template = Template.fromStack(stack);
  });

  describe('Cognito User Pool', () => {
    test('creates user pool with correct configuration', () => {
      template.hasResourceProperties('AWS::Cognito::UserPool', {
        UserPoolName: 'organize-dctech-events-users',
        AutoVerifiedAttributes: ['email'],
        AliasAttributes: ['email'],
        Schema: Match.arrayWith([
          Match.objectLike({
            Name: 'email',
            Required: true,
            Mutable: true,
          }),
        ]),
      });
    });

    test('creates user pool client with OAuth configuration', () => {
      template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
        AllowedOAuthFlows: ['implicit', 'code'],
        AllowedOAuthScopes: ['email', 'openid', 'profile'],
        GenerateSecret: false,
      });
    });

    test('creates user pool domain', () => {
      template.hasResourceProperties('AWS::Cognito::UserPoolDomain', {
        Domain: 'organize-dctech-events',
      });
    });
  });

  describe('DynamoDB Tables', () => {
    test('creates users table with correct configuration', () => {
      template.hasResourceProperties('AWS::DynamoDB::Table', {
        TableName: 'organize-users',
        KeySchema: [
          {
            AttributeName: 'userId',
            KeyType: 'HASH',
          },
        ],
        BillingMode: 'PAY_PER_REQUEST',
        PointInTimeRecoverySpecification: {
          PointInTimeRecoveryEnabled: true,
        },
      });
    });

    test('creates groups table with active groups index', () => {
      template.hasResourceProperties('AWS::DynamoDB::Table', {
        TableName: 'organize-groups',
        GlobalSecondaryIndexes: Match.arrayWith([
          Match.objectLike({
            IndexName: 'activeGroupsIndex',
            KeySchema: [
              { AttributeName: 'active', KeyType: 'HASH' },
              { AttributeName: 'createdAt', KeyType: 'RANGE' },
            ],
          }),
        ]),
      });
    });

    test('creates group members table with user groups index', () => {
      template.hasResourceProperties('AWS::DynamoDB::Table', {
        TableName: 'organize-group-members',
        GlobalSecondaryIndexes: Match.arrayWith([
          Match.objectLike({
            IndexName: 'userGroupsIndex',
          }),
        ]),
      });
    });

    test('creates events table with multiple indices', () => {
      template.hasResourceProperties('AWS::DynamoDB::Table', {
        TableName: 'organize-events',
        GlobalSecondaryIndexes: Match.arrayWith([
          Match.objectLike({ IndexName: 'groupEventsIndex' }),
          Match.objectLike({ IndexName: 'dateEventsIndex' }),
        ]),
      });
    });

    test('creates rsvps table with user RSVPs index', () => {
      template.hasResourceProperties('AWS::DynamoDB::Table', {
        TableName: 'organize-rsvps',
        GlobalSecondaryIndexes: Match.arrayWith([
          Match.objectLike({ IndexName: 'userRSVPsIndex' }),
        ]),
      });
    });

    test('creates messages table', () => {
      template.hasResourceProperties('AWS::DynamoDB::Table', {
        TableName: 'organize-messages',
        KeySchema: [
          { AttributeName: 'groupId', KeyType: 'HASH' },
          { AttributeName: 'timestamp', KeyType: 'RANGE' },
        ],
      });
    });
  });

  describe('S3 and CloudFront', () => {
    test('creates S3 bucket with website configuration', () => {
      template.hasResourceProperties('AWS::S3::Bucket', {
        WebsiteConfiguration: {
          IndexDocument: 'index.html',
          ErrorDocument: 'index.html',
        },
        PublicAccessBlockConfiguration: {
          BlockPublicAcls: true,
          BlockPublicPolicy: true,
          IgnorePublicAcls: true,
          RestrictPublicBuckets: true,
        },
        CorsConfiguration: {
          CorsRules: [
            {
              AllowedMethods: ['GET'],
              AllowedOrigins: ['*'],
              AllowedHeaders: ['*'],
            },
          ],
        },
      });
    });

    test('creates CloudFront distribution with custom domain', () => {
      template.hasResourceProperties('AWS::CloudFront::Distribution', {
        DistributionConfig: Match.objectLike({
          Aliases: ['organize.dctech.events'],
          DefaultRootObject: 'index.html',
          CustomErrorResponses: Match.arrayWith([
            {
              ErrorCode: 404,
              ResponseCode: 200,
              ResponsePagePath: '/index.html',
            },
            {
              ErrorCode: 403,
              ResponseCode: 200,
              ResponsePagePath: '/index.html',
            },
          ]),
        }),
      });
    });

    test('creates origin access identity for CloudFront', () => {
      template.resourceCountIs('AWS::CloudFront::CloudFrontOriginAccessIdentity', 1);
    });
  });

  describe('Route 53 DNS', () => {
    test('creates A record for organize subdomain', () => {
      template.hasResourceProperties('AWS::Route53::RecordSet', {
        Name: 'organize.dctech.events.',
        Type: 'A',
      });
    });

    test('creates AAAA record for IPv6 support', () => {
      template.hasResourceProperties('AWS::Route53::RecordSet', {
        Name: 'organize.dctech.events.',
        Type: 'AAAA',
      });
    });
  });

  describe('Lambda Functions', () => {
    test('creates API Lambda function with correct runtime', () => {
      template.hasResourceProperties('AWS::Lambda::Function', {
        Runtime: 'nodejs20.x',
        Handler: 'index.handler',
        Timeout: 30,
        MemorySize: 512,
        Environment: {
          Variables: Match.objectLike({
            USERS_TABLE: Match.anyValue(),
            GROUPS_TABLE: Match.anyValue(),
            EVENTS_TABLE: Match.anyValue(),
          }),
        },
      });
    });

    test('creates export Lambda function with longer timeout', () => {
      template.hasResourceProperties('AWS::Lambda::Function', {
        Runtime: 'nodejs20.x',
        Timeout: 300,
        MemorySize: 1024,
      });
    });

    test('grants DynamoDB read/write permissions to API Lambda', () => {
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Action: Match.arrayWith([
                'dynamodb:BatchGetItem',
                'dynamodb:GetItem',
                'dynamodb:Scan',
                'dynamodb:PutItem',
                'dynamodb:UpdateItem',
              ]),
            }),
          ]),
        },
      });
    });

    test('grants Cognito permissions to API Lambda', () => {
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Action: ['cognito-idp:GetUser', 'cognito-idp:AdminGetUser'],
            }),
          ]),
        },
      });
    });
  });

  describe('API Gateway', () => {
    test('creates REST API with CORS configuration', () => {
      template.hasResourceProperties('AWS::ApiGateway::RestApi', {
        Name: 'Organize DC Tech Events API',
      });
    });

    test('creates proxy resource for Lambda integration', () => {
      template.hasResourceProperties('AWS::ApiGateway::Resource', {
        PathPart: '{proxy+}',
      });
    });

    test('creates ANY method for proxy resource', () => {
      template.hasResourceProperties('AWS::ApiGateway::Method', {
        HttpMethod: 'ANY',
        AuthorizationType: 'NONE',
      });
    });
  });

  describe('EventBridge', () => {
    test('creates scheduled rule for export Lambda', () => {
      template.hasResourceProperties('AWS::Events::Rule', {
        ScheduleExpression: 'rate(5 minutes)',
      });
    });

    test('configures export Lambda as rule target', () => {
      template.hasResourceProperties('AWS::Events::Rule', {
        Targets: Match.arrayWith([
          Match.objectLike({
            Arn: Match.anyValue(),
          }),
        ]),
      });
    });
  });

  describe('Stack Outputs', () => {
    test('exports all required outputs', () => {
      const outputs = Object.keys(template.findOutputs('*'));
      
      expect(outputs).toContain('UserPoolId');
      expect(outputs).toContain('UserPoolClientId');
      expect(outputs).toContain('ApiUrl');
      expect(outputs).toContain('CloudFrontUrl');
      expect(outputs).toContain('WebsiteBucketName');
    });
  });

  describe('Resource Count', () => {
    test('creates expected number of DynamoDB tables', () => {
      template.resourceCountIs('AWS::DynamoDB::Table', 6);
    });

    test('creates expected number of Lambda functions', () => {
      template.resourceCountIs('AWS::Lambda::Function', 2);
    });

    test('creates single API Gateway', () => {
      template.resourceCountIs('AWS::ApiGateway::RestApi', 1);
    });

    test('creates single CloudFront distribution', () => {
      template.resourceCountIs('AWS::CloudFront::Distribution', 1);
    });
  });
});
