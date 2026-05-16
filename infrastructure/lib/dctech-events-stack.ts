import * as cdk from 'aws-cdk-lib/core';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import { Construct } from 'constructs';
import { stackConfig } from './config';

const githubPagesARecords = [
  '185.199.108.153',
  '185.199.109.153',
  '185.199.110.153',
  '185.199.111.153',
];

const githubPagesAaaaRecords = [
  '2606:50c0:8000::153',
  '2606:50c0:8001::153',
  '2606:50c0:8002::153',
  '2606:50c0:8003::153',
];

export class DctechEventsStack extends cdk.Stack {
  public readonly certificate: acm.ICertificate;
  public readonly eventsTable: dynamodb.Table;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Data Cache Bucket (for _cache and _data syncing)
    const dataCacheBucket = new s3.Bucket(this, 'DataCacheBucket', {
      bucketName: stackConfig.s3.dataCacheBucketName,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: false,
      encryption: s3.BucketEncryption.S3_MANAGED,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // DynamoDB Table for Events
    this.eventsTable = new dynamodb.Table(this, 'EventsTable', {
      tableName: stackConfig.dynamodb.tableName,
      partitionKey: { name: 'eventId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // GSI: Query by Date (Next 14 days, By Month)
    this.eventsTable.addGlobalSecondaryIndex({
      indexName: 'DateIndex',
      partitionKey: { name: 'status', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'date', type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // GSI: Query by Created Date (Recently Added)
    this.eventsTable.addGlobalSecondaryIndex({
      indexName: 'CreatedIndex',
      partitionKey: { name: 'status', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'createdAt', type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // Phase 1.5: Route53 Hosted Zone lookup (required for certificate validation and DNS records)
    let hostedZone: route53.IHostedZone | undefined;
    if (stackConfig.hostedZoneId) {
      hostedZone = route53.HostedZone.fromHostedZoneAttributes(this, 'DctechEventsHostedZone', {
        hostedZoneId: stackConfig.hostedZoneId,
        zoneName: stackConfig.domain,
      });
    }

    // Phase 1.4: SSL/TLS Certificate (reference existing or create new)
    if (stackConfig.acm.existingCertificateArn) {
      this.certificate = acm.Certificate.fromCertificateArn(
        this,
        'DctechEventsCertificate',
        stackConfig.acm.existingCertificateArn
      );
    } else {
      if (!hostedZone) {
        throw new Error(
          'HOSTED_ZONE_ID environment variable must be set to create a new certificate with DNS validation'
        );
      }
      this.certificate = new acm.Certificate(this, 'DctechEventsCertificate', {
        domainName: stackConfig.acm.domainName,
        subjectAlternativeNames: stackConfig.acm.alternativeNames,
        validation: acm.CertificateValidation.fromDns(hostedZone),
      });
    }

    const certificate = this.certificate;

    // Phase 1.7: GitHub OIDC Federation
    // Create OIDC identity provider
    const oidcProvider = new iam.OpenIdConnectProvider(this, 'GitHubOIDCProvider', {
      url: stackConfig.github.oidcProviderUrl,
      clientIds: [stackConfig.github.oidcClientId],
      thumbprints: [stackConfig.github.oidcThumbprint],
    });

    // Create IAM role for GitHub Actions
    const githubActionsRole = new iam.Role(this, 'GithubActionsDeployRole', {
      roleName: stackConfig.iam.roleName,
      assumedBy: new iam.WebIdentityPrincipal(
        oidcProvider.openIdConnectProviderArn,
        {
          StringEquals: {
            'token.actions.githubusercontent.com:aud': stackConfig.github.oidcClientId,
          },
          StringLike: {
            'token.actions.githubusercontent.com:sub': `repo:${stackConfig.github.repositoryOwner}/${stackConfig.github.repositoryName}:${stackConfig.github.ref}`,
          },
        }
      ),
      maxSessionDuration: cdk.Duration.seconds(stackConfig.iam.sessionDuration),
    });

    githubActionsRole.attachInlinePolicy(
      new iam.Policy(this, 'GithubActionsDeployPolicy', {
        statements: [
          new iam.PolicyStatement({
            actions: [
              's3:GetObject',
              's3:PutObject',
              's3:DeleteObject',
              's3:ListBucket',
            ],
            resources: [`arn:aws:s3:::dctech-events-*`, `arn:aws:s3:::dctech-events-*/*`],
          }),
          new iam.PolicyStatement({
            actions: ['cloudfront:CreateInvalidation'],
            resources: [`arn:aws:cloudfront::${cdk.Stack.of(this).account}:distribution/*`],
          }),
          new iam.PolicyStatement({
            actions: ['cloudfront:ListDistributions'],
            resources: ['*'],
          }),
          new iam.PolicyStatement({
            actions: [
              'dynamodb:PutItem',
              'dynamodb:GetItem',
              'dynamodb:UpdateItem',
              'dynamodb:DeleteItem',
              'dynamodb:BatchWriteItem',
              'dynamodb:Query',
              'dynamodb:Scan',
            ],
            resources: [this.eventsTable.tableArn, `${this.eventsTable.tableArn}/index/*`],
          }),
          new iam.PolicyStatement({
            actions: ['sqs:SendMessage', 'sqs:GetQueueUrl'],
            resources: [`arn:aws:sqs:${this.region}:${this.account}:${stackConfig.rebuild.queueName}`],
          }),
          new iam.PolicyStatement({
            actions: ['sts:AssumeRole'],
            resources: [
              `arn:aws:iam::${cdk.Stack.of(this).account}:role/cdk-hnb659fds-deploy-role-${cdk.Stack.of(this).account}-*`,
              `arn:aws:iam::${cdk.Stack.of(this).account}:role/cdk-hnb659fds-file-publishing-role-${cdk.Stack.of(this).account}-*`,
              `arn:aws:iam::${cdk.Stack.of(this).account}:role/cdk-hnb659fds-image-publishing-role-${cdk.Stack.of(this).account}-*`,
              `arn:aws:iam::${cdk.Stack.of(this).account}:role/cdk-hnb659fds-lookup-role-${cdk.Stack.of(this).account}-*`,
            ],
          }),
          new iam.PolicyStatement({
            actions: [
              'ecr:GetAuthorizationToken',
              'ecr:BatchCheckLayerAvailability',
              'ecr:GetDownloadUrlForLayer',
              'ecr:GetRepositoryPolicy',
              'ecr:DescribeRepositories',
              'ecr:ListImages',
              'ecr:DescribeImages',
              'ecr:BatchGetImage',
              'ecr:InitiateLayerUpload',
              'ecr:UploadLayerPart',
              'ecr:CompleteLayerUpload',
              'ecr:PutImage',
            ],
            resources: ['*'],
          }),
        ],
      })
    );

    // GitHub Pages DNS records
    if (hostedZone) {
      new route53.ARecord(this, 'DctechEventsARecord', {
        zone: hostedZone,
        target: route53.RecordTarget.fromIpAddresses(...githubPagesARecords),
        recordName: stackConfig.domain,
        comment: 'IPv4 record for dctech.events pointing to GitHub Pages',
      });

      new route53.AaaaRecord(this, 'DctechEventsAAAARecord', {
        zone: hostedZone,
        target: route53.RecordTarget.fromIpAddresses(...githubPagesAaaaRecords),
        recordName: stackConfig.domain,
        comment: 'IPv6 record for dctech.events pointing to GitHub Pages',
      });

      new route53.ARecord(this, 'WwwDctechEventsARecord', {
        zone: hostedZone,
        target: route53.RecordTarget.fromIpAddresses(...githubPagesARecords),
        recordName: 'www',
        comment: 'IPv4 record for www.dctech.events pointing to GitHub Pages',
      });

      new route53.AaaaRecord(this, 'WwwDctechEventsAAAARecord', {
        zone: hostedZone,
        target: route53.RecordTarget.fromIpAddresses(...githubPagesAaaaRecords),
        recordName: 'www',
        comment: 'IPv6 record for www.dctech.events pointing to GitHub Pages',
      });
    } else {
      new cdk.CfnOutput(this, 'DNSRecordsNote', {
        value: 'Hosted zone not configured. Please set HOSTED_ZONE_ID to create DNS records.',
        description: 'DNS records configuration status',
      });
    }

    // Stack outputs
    new cdk.CfnOutput(this, 'DataCacheBucketName', {
      value: dataCacheBucket.bucketName,
      description: 'S3 bucket name for data cache',
      exportName: 'DctechEventsDataCacheBucketName',
    });

    new cdk.CfnOutput(this, 'CertificateArn', {
      value: certificate.certificateArn,
      description: 'ACM Certificate ARN used for HTTPS',
      exportName: 'DctechEventsCertificateArn',
    });

    new cdk.CfnOutput(this, 'GithubActionsRoleArn', {
      value: githubActionsRole.roleArn,
      description: 'IAM role ARN for GitHub Actions',
      exportName: 'DctechEventsGithubActionsRoleArn',
    });

    cdk.Tags.of(this).add('project', stackConfig.tags.project);
    cdk.Tags.of(this).add('environment', stackConfig.tags.environment);
    cdk.Tags.of(this).add('managedBy', stackConfig.tags.managedBy);
  }
}
