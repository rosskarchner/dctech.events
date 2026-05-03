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
  public readonly distribution: cloudfront.IDistribution;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Phase 1.2: S3 Bucket for static site hosting (import existing bucket)
    // The bucket is created outside of CloudFormation and imported here
    const siteBucket = s3.Bucket.fromBucketName(this, 'DcstemEventsSiteBucket', dcstemStackConfig.s3.bucketName);

    // Data Cache Bucket (import existing)
    const dataCacheBucket = s3.Bucket.fromBucketName(this, 'DcstemDataCacheBucket', dcstemStackConfig.s3.dataCacheBucketName);

    // Note: DynamoDB Table is created once in dctech stack and shared across all sites
    // Do not create a duplicate table here

    // Create Origin Access Control for CloudFront (modern replacement for OAI)
    // Note: This is not used since we're importing an existing distribution
    // const oac = new cloudfront.S3OriginAccessControl(this, 'DcstemS3OAC', {
    //   description: 'OAC for DC Tech Events S3 bucket',
    // });

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

    // Phase 1.4: SSL/TLS Certificate (reference existing)
    // Note: Certificate MUST be in us-east-1 for CloudFront
    this.certificate = acm.Certificate.fromCertificateArn(
      this,
      'DcstemEventsCertificate',
      dcstemStackConfig.acm.existingCertificateArn
    );

    // Phase 1.3: CloudFront Distribution (import existing)
    // The distribution already exists with the correct aliases and certificate configuration
    this.distribution = cloudfront.Distribution.fromDistributionAttributes(
      this,
      'DcstemEventsDistribution',
      {
        distributionId: 'E1L518FFFF90DJ',
        domainName: 'dhur7tb7r7w8g.cloudfront.net',
      }
    );

    // Note: Bucket policy not needed for imported distribution since it's already configured

    // Phase 1.7: GitHub OIDC Federation
    // Note: OIDC provider and IAM role are created once in dctech-events-stack (shared)
    // The policy already includes permissions for both dctech-events-* and dcstem-events-*
    // Just import the existing role without modifying it
    const githubActionsRole = iam.Role.fromRoleName(
      this,
      'GithubActionsDeployRole',
      dcstemStackConfig.iam.roleName
    );

    // Phase 1.6: Route53 DNS Records (requires hosted zone)
    // Create A and AAAA records for IPv4 and IPv6 support
    if (hostedZone) {
      // Create A record (IPv4) - points to CloudFront distribution
      new route53.ARecord(this, 'DcstemEventsARecord', {
        zone: hostedZone,
        target: route53.RecordTarget.fromAlias(
          new route53targets.CloudFrontTarget(this.distribution)
        ),
        recordName: dcstemStackConfig.domain,
        comment: 'IPv4 record for dc.localstem.events pointing to CloudFront',
      });

      // Create AAAA record (IPv6) - points to CloudFront distribution
      new route53.AaaaRecord(this, 'DcstemEventsAAAARecord', {
        zone: hostedZone,
        target: route53.RecordTarget.fromAlias(
          new route53targets.CloudFrontTarget(this.distribution)
        ),
        recordName: dcstemStackConfig.domain,
        comment: 'IPv6 record for dc.localstem.events pointing to CloudFront',
      });

      new route53.ARecord(this, 'WwwDcstemEventsARecord', {
        zone: hostedZone,
        target: route53.RecordTarget.fromAlias(
          new route53targets.CloudFrontTarget(this.distribution)
        ),
        recordName: 'www.dc.localstem.events',
        comment: 'IPv4 record for www.dc.localstem.events pointing to the main CloudFront distribution',
      });

      new route53.AaaaRecord(this, 'WwwDcstemEventsAAAARecord', {
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
      exportName: 'DcstemEventsBucketName',
    });

    new cdk.CfnOutput(this, 'DataCacheBucketName', {
      value: dataCacheBucket.bucketName,
      description: 'S3 bucket name for data cache',
      exportName: 'DcstemEventsDataCacheBucketName',
    });

    new cdk.CfnOutput(this, 'CloudFrontDistributionId', {
      value: 'E1L518FFFF90DJ',
      description: 'CloudFront distribution ID',
      exportName: 'DcstemEventsDistributionId',
    });

    new cdk.CfnOutput(this, 'CloudFrontDomainName', {
      value: 'dhur7tb7r7w8g.cloudfront.net',
      description: 'CloudFront domain name',
      exportName: 'DcstemEventsCloudFrontDomain',
    });

    new cdk.CfnOutput(this, 'CertificateArn', {
      value: this.certificate.certificateArn,
      description: 'ACM Certificate ARN used for HTTPS',
      exportName: 'DcstemEventsCertificateArn',
    });

    new cdk.CfnOutput(this, 'GithubActionsRoleArn', {
      value: githubActionsRole.roleArn,
      description: 'IAM role ARN for GitHub Actions',
      exportName: 'DcstemEventsGithubActionsRoleArn',
    });

    // Apply tags to all resources
    cdk.Tags.of(this).add('project', dcstemStackConfig.tags.project);
    cdk.Tags.of(this).add('environment', dcstemStackConfig.tags.environment);
    cdk.Tags.of(this).add('managedBy', dcstemStackConfig.tags.managedBy);
  }
}
