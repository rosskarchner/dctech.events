import * as cdk from 'aws-cdk-lib/core';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as route53targets from 'aws-cdk-lib/aws-route53-targets';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import { Construct } from 'constructs';
import { stackConfig } from './config';

export interface FrontendStackProps extends cdk.StackProps {
  certificate: acm.ICertificate;
}

export class FrontendStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: FrontendStackProps) {
    super(scope, id, props);

    const { certificate } = props;

    // Hosted zone lookup
    const hostedZone = route53.HostedZone.fromHostedZoneAttributes(
      this,
      'HostedZone',
      {
        hostedZoneId: stackConfig.hostedZoneId,
        zoneName: stackConfig.domain,
      }
    );

    // Origin Access Control for CloudFront
    const oac = new cloudfront.S3OriginAccessControl(this, 'FrontendOAC', {
      description: 'OAC for DC Tech Events frontend app buckets',
    });

    // CloudFront Function to rewrite directory URLs to index.html
    const directoryIndexFunction = new cloudfront.Function(this, 'DirectoryIndexFunction', {
      code: cloudfront.FunctionCode.fromInline(`
function handler(event) {
  var request = event.request;
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
      comment: 'Rewrite directory URLs to index.html for frontend apps',
      functionName: 'dctech-events-frontend-directory-index',
    });

    // Define the two frontend sites
    const sites = [
      { subdomain: 'suggest', bucketName: 'dctech-events-suggest-frontend' },
      { subdomain: 'manage', bucketName: 'dctech-events-manage-frontend' },
    ];

    for (const site of sites) {
      const domainName = `${site.subdomain}.${stackConfig.domain}`;
      const idPrefix = site.subdomain.charAt(0).toUpperCase() + site.subdomain.slice(1);

      // S3 Bucket
      const bucket = new s3.Bucket(this, `${idPrefix}Bucket`, {
        bucketName: site.bucketName,
        blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
        versioned: false,
        encryption: s3.BucketEncryption.S3_MANAGED,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
        autoDeleteObjects: true,
      });

      // CloudFront Distribution
      const distribution = new cloudfront.Distribution(this, `${idPrefix}Distribution`, {
        defaultBehavior: {
          origin: origins.S3BucketOrigin.withOriginAccessControl(bucket, {
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
        defaultRootObject: 'index.html',
        domainNames: [domainName],
        certificate: certificate,
        httpVersion: cloudfront.HttpVersion.HTTP2_AND_3,
        enableIpv6: true,
        minimumProtocolVersion: cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
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

      // Bucket policy for CloudFront OAC
      bucket.addToResourcePolicy(
        new iam.PolicyStatement({
          actions: ['s3:GetObject'],
          resources: [bucket.arnForObjects('*')],
          principals: [new iam.ServicePrincipal('cloudfront.amazonaws.com')],
          conditions: {
            StringEquals: {
              'AWS:SourceArn': `arn:aws:cloudfront::${cdk.Stack.of(this).account}:distribution/${distribution.distributionId}`,
            },
          },
        })
      );

      // Route53 A record (IPv4)
      new route53.ARecord(this, `${idPrefix}ARecord`, {
        zone: hostedZone,
        target: route53.RecordTarget.fromAlias(
          new route53targets.CloudFrontTarget(distribution)
        ),
        recordName: domainName,
        comment: `IPv4 record for ${domainName} pointing to CloudFront`,
      });

      // Route53 AAAA record (IPv6)
      new route53.AaaaRecord(this, `${idPrefix}AAAARecord`, {
        zone: hostedZone,
        target: route53.RecordTarget.fromAlias(
          new route53targets.CloudFrontTarget(distribution)
        ),
        recordName: domainName,
        comment: `IPv6 record for ${domainName} pointing to CloudFront`,
      });

      // Outputs
      new cdk.CfnOutput(this, `${idPrefix}BucketName`, {
        value: bucket.bucketName,
        description: `S3 bucket name for ${domainName}`,
      });

      new cdk.CfnOutput(this, `${idPrefix}DistributionId`, {
        value: distribution.distributionId,
        description: `CloudFront distribution ID for ${domainName}`,
      });

      new cdk.CfnOutput(this, `${idPrefix}DistributionDomain`, {
        value: distribution.domainName,
        description: `CloudFront domain name for ${domainName}`,
      });
    }

    // Apply tags to all resources
    cdk.Tags.of(this).add('project', stackConfig.tags.project);
    cdk.Tags.of(this).add('environment', stackConfig.tags.environment);
    cdk.Tags.of(this).add('managedBy', stackConfig.tags.managedBy);
  }
}
