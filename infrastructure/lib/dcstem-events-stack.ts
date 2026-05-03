import * as cdk from 'aws-cdk-lib/core';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as route53targets from 'aws-cdk-lib/aws-route53-targets';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import { Construct } from 'constructs';
import { dcstemStackConfig } from './config';

export class DcstemEventsStack extends cdk.Stack {
  public readonly certificate: acm.ICertificate;
  public readonly distribution: cloudfront.Distribution;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Phase 1.2: S3 Bucket for static site hosting
    const siteBucket = new s3.Bucket(this, 'DcstemEventsSiteBucket', {
      bucketName: dcstemStackConfig.s3.bucketName,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: dcstemStackConfig.s3.versioningEnabled,
      encryption: s3.BucketEncryption.S3_MANAGED,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // For development; use RETAIN in production
      autoDeleteObjects: true,
    });

    // Data Cache Bucket (for _cache and _data syncing)
    const dataCacheBucket = new s3.Bucket(this, 'DcstemDataCacheBucket', {
      bucketName: dcstemStackConfig.s3.dataCacheBucketName,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: false,
      encryption: s3.BucketEncryption.S3_MANAGED,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // Note: DynamoDB Table is created once in dctech stack and shared across all sites
    // Do not create a duplicate table here

    // Create Origin Access Control for CloudFront (modern replacement for OAI)
    const oac = new cloudfront.S3OriginAccessControl(this, 'DcstemS3OAC', {
      description: 'OAC for DC Tech Events S3 bucket',
    });

    // Phase 1.5: Route53 Hosted Zone lookup (required for certificate validation and DNS records)
    // Note: Hosted zone must exist in the same AWS account
    let hostedZone: route53.IHostedZone | undefined;
    if (dcstemStackConfig.hostedZoneId) {
      hostedZone = route53.HostedZone.fromHostedZoneAttributes(
        this,
        'DcstemEventsHostedZone',
        {
          hostedZoneId: dcstemStackConfig.hostedZoneId,
          zoneName: dcstemStackConfig.domain,
        }
      );
    }

    // Phase 1.4: SSL/TLS Certificate (reference existing or create new)
    // Note: Certificate MUST be in us-east-1 for CloudFront
    if (dcstemStackConfig.acm.existingCertificateArn) {
      this.certificate = acm.Certificate.fromCertificateArn(
        this,
        'DcstemEventsCertificate',
        dcstemStackConfig.acm.existingCertificateArn
      );
    } else {
      if (!hostedZone) {
        throw new Error(
          'HOSTED_ZONE_ID environment variable must be set to create a new certificate with DNS validation'
        );
      }
      // Create certificate with DNS validation using the hosted zone
      // This will automatically create the DNS validation records in Route53
      this.certificate = new acm.Certificate(this, 'DcstemEventsCertificate', {
        domainName: dcstemStackConfig.acm.domainName,
        subjectAlternativeNames: dcstemStackConfig.acm.alternativeNames,
        validation: acm.CertificateValidation.fromDns(hostedZone),
      });
    }

    const certificate = this.certificate;
    const distributionDomains = [dcstemStackConfig.domain, 'www.dc.localstem.events'];

    // CloudFront Function to rewrite directory URLs to index.html
    // This allows /locations/dc/ to serve /locations/dc/index.html
    const directoryIndexFunction = new cloudfront.Function(this, 'DirectoryIndexFunction', {
      code: cloudfront.FunctionCode.fromInline(`
function handler(event) {
  var request = event.request;
  var headers = request.headers;
  var host = headers.host ? headers.host.value : '';

  if (host === 'www.dc.localstem.events') {
    return {
      statusCode: 301,
      statusDescription: 'Moved Permanently',
      headers: {
        'location': { 'value': 'https://${dcstemStackConfig.domain}' + request.uri }
      }
    };
  }

  var uri = request.uri;

  // If URI ends with '/', append 'index.html'
  if (uri.endsWith('/')) {
    request.uri += 'index.html';
  }
  // If URI has no extension, append '/index.html'
  else if (!uri.includes('.')) {
    request.uri += '/index.html';
  }

  return request;
}
      `),
      comment: 'Rewrite directory URLs to index.html',
      functionName: 'dcstem-events-directory-index',
    });

    // Phase 1.3: CloudFront Distribution
    // Web ACL must be explicitly declared to prevent CloudFormation from trying to remove it
    this.distribution = new cloudfront.Distribution(this, 'DcstemEventsDistribution', {
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(siteBucket, {
          originAccessControl: oac,
        }),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        compress: dcstemStackConfig.cloudfront.enableCompression,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        functionAssociations: [
          {
            function: directoryIndexFunction,
            eventType: cloudfront.FunctionEventType.VIEWER_REQUEST,
          },
        ],
      },
      defaultRootObject: 'index.html',
      domainNames: distributionDomains,
      certificate: certificate,
      httpVersion: cloudfront.HttpVersion.HTTP2_AND_3,
      enableIpv6: true,
      minimumProtocolVersion: cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
      webAclId: dcstemStackConfig.cloudfront.webAclId,
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 404,
          responsePagePath: '/404.html',
          ttl: cdk.Duration.minutes(5),
        },
        {
          httpStatus: 404,
          responseHttpStatus: 404,
          responsePagePath: '/404.html',
          ttl: cdk.Duration.minutes(5),
        },
      ],
    });

    // Add bucket policy to allow CloudFront OAC to access S3
    siteBucket.addToResourcePolicy(
      new iam.PolicyStatement({
        actions: ['s3:GetObject'],
        resources: [siteBucket.arnForObjects('*')],
        principals: [new iam.ServicePrincipal('cloudfront.amazonaws.com')],
        conditions: {
          StringEquals: {
            'AWS:SourceArn': `arn:aws:cloudfront::${cdk.Stack.of(this).account}:distribution/${
              this.distribution.distributionId
            }`,
          },
        },
      })
    );

    // Phase 1.7: GitHub OIDC Federation
    // Create OIDC identity provider
    const oidcProvider = new iam.OpenIdConnectProvider(
      this,
      'GitHubOIDCProvider',
      {
        url: dcstemStackConfig.github.oidcProviderUrl,
        clientIds: [dcstemStackConfig.github.oidcClientId],
        thumbprints: [dcstemStackConfig.github.oidcThumbprint],
      }
    );

    // Create IAM role for GitHub Actions
    const githubActionsRole = new iam.Role(this, 'GithubActionsDeployRole', {
      roleName: dcstemStackConfig.iam.roleName,
      assumedBy: new iam.WebIdentityPrincipal(
        oidcProvider.openIdConnectProviderArn,
        {
          StringEquals: {
            'token.actions.githubusercontent.com:aud': dcstemStackConfig.github.oidcClientId,
          },
          StringLike: {
            'token.actions.githubusercontent.com:sub': `repo:${dcstemStackConfig.github.repositoryOwner}/${dcstemStackConfig.github.repositoryName}:${dcstemStackConfig.github.ref}`,
          },
        }
      ),
      maxSessionDuration: cdk.Duration.seconds(dcstemStackConfig.iam.sessionDuration),
    });

    // Add inline policy for S3 + CloudFront permissions
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
            resources: [
              `arn:aws:s3:::dctech-events-*`,
              `arn:aws:s3:::dctech-events-*/*`,
            ],
          }),
          new iam.PolicyStatement({
            actions: ['cloudfront:CreateInvalidation'],
            resources: [
              `arn:aws:cloudfront::${cdk.Stack.of(this).account}:distribution/*`,
            ],
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
            actions: [
              'sqs:SendMessage',
              'sqs:GetQueueUrl',
            ],
            resources: [`arn:aws:sqs:${this.region}:${this.account}:${dcstemStackConfig.rebuild.queueName}`],
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
            resources: ['*'], // Standard for CDK ECR access
          }),
        ],
      })
    );

    // Phase 1.6: Route53 DNS Records (requires hosted zone)
    // Create A and AAAA records for IPv4 and IPv6 support
    if (hostedZone) {
      // Create A record (IPv4) - points to CloudFront distribution
      new route53.ARecord(this, 'DctechEventsARecord', {
        zone: hostedZone,
        target: route53.RecordTarget.fromAlias(
          new route53targets.CloudFrontTarget(this.distribution)
        ),
        recordName: dcstemStackConfig.domain,
        comment: 'IPv4 record for dctech.events pointing to CloudFront',
      });

      // Create AAAA record (IPv6) - points to CloudFront distribution
      new route53.AaaaRecord(this, 'DctechEventsAAAARecord', {
        zone: hostedZone,
        target: route53.RecordTarget.fromAlias(
          new route53targets.CloudFrontTarget(this.distribution)
        ),
        recordName: dcstemStackConfig.domain,
        comment: 'IPv6 record for dctech.events pointing to CloudFront',
      });

      new route53.ARecord(this, 'WwwDctechEventsARecord', {
        zone: hostedZone,
        target: route53.RecordTarget.fromAlias(
          new route53targets.CloudFrontTarget(this.distribution)
        ),
        recordName: 'www.dc.localstem.events',
        comment: 'IPv4 record for www.dc.localstem.events pointing to the main CloudFront distribution',
      });

      new route53.AaaaRecord(this, 'WwwDctechEventsAAAARecord', {
        zone: hostedZone,
        target: route53.RecordTarget.fromAlias(
          new route53targets.CloudFrontTarget(this.distribution)
        ),
        recordName: 'www.dc.localstem.events',
        comment: 'IPv6 record for www.dc.localstem.events pointing to the main CloudFront distribution',
      });
    } else {
      // Output message if hosted zone is not configured
      new cdk.CfnOutput(this, 'DNSRecordsNote', {
        value: 'Hosted zone not configured. Please set HOSTED_ZONE_ID to create DNS records.',
        description: 'DNS records configuration status',
      });
    }

    // Phase 1.8: Stack outputs
    new cdk.CfnOutput(this, 'S3BucketName', {
      value: siteBucket.bucketName,
      description: 'S3 bucket name for static site',
      exportName: 'DctechEventsBucketName',
    });

    new cdk.CfnOutput(this, 'DataCacheBucketName', {
      value: dataCacheBucket.bucketName,
      description: 'S3 bucket name for data cache',
      exportName: 'DctechEventsDataCacheBucketName',
    });

    new cdk.CfnOutput(this, 'CloudFrontDistributionId', {
      value: this.distribution.distributionId,
      description: 'CloudFront distribution ID',
      exportName: 'DctechEventsDistributionId',
    });

    new cdk.CfnOutput(this, 'CloudFrontDomainName', {
      value: this.distribution.domainName,
      description: 'CloudFront domain name',
      exportName: 'DctechEventsCloudFrontDomain',
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

    // Apply tags to all resources
    cdk.Tags.of(this).add('project', dcstemStackConfig.tags.project);
    cdk.Tags.of(this).add('environment', dcstemStackConfig.tags.environment);
    cdk.Tags.of(this).add('managedBy', dcstemStackConfig.tags.managedBy);
  }
}
