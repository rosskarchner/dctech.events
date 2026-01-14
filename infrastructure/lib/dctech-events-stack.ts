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

export class DctechEventsStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Phase 1.2: S3 Bucket for static site hosting
    const siteBucket = new s3.Bucket(this, 'DctechEventsSiteBucket', {
      bucketName: stackConfig.s3.bucketName,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: stackConfig.s3.versioningEnabled,
      encryption: s3.BucketEncryption.S3_MANAGED,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // For development; use RETAIN in production
      autoDeleteObjects: true,
    });

    // Create Origin Access Identity for CloudFront
    const oai = new cloudfront.OriginAccessIdentity(this, 'S3OAI', {
      comment: 'OAI for DC Tech Events S3 bucket',
    });

    // Grant CloudFront OAI read access to S3 bucket
    siteBucket.grantRead(oai);

    // Phase 1.4: SSL/TLS Certificate (reference existing or create new)
    let certificate: acm.ICertificate;
    if (stackConfig.acm.existingCertificateArn) {
      certificate = acm.Certificate.fromCertificateArn(
        this,
        'DctechEventsCertificate',
        stackConfig.acm.existingCertificateArn
      );
    } else {
      certificate = new acm.Certificate(this, 'DctechEventsCertificate', {
        domainName: stackConfig.acm.domainName,
        subjectAlternativeNames: stackConfig.acm.alternativeNames,
        validation: acm.CertificateValidation.fromDns(),
      });
    }

    // Phase 1.3: CloudFront Distribution
    const distribution = new cloudfront.Distribution(this, 'DctechEventsDistribution', {
      defaultBehavior: {
        origin: new origins.S3Origin(siteBucket, {
          originAccessIdentity: oai,
        }),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        compress: stackConfig.cloudfront.enableCompression,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
      },
      defaultRootObject: 'index.html',
      domainNames: [stackConfig.domain],
      certificate: certificate,
      httpVersion: cloudfront.HttpVersion.HTTP2_AND_3,
      enableIpv6: true,
      minimumProtocolVersion: cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
    });

    // Phase 1.6: GitHub OIDC Federation
    // Create OIDC identity provider
    const oidcProvider = new iam.OpenIdConnectProvider(
      this,
      'GitHubOIDCProvider',
      {
        url: stackConfig.github.oidcProviderUrl,
        clientIds: [stackConfig.github.oidcClientId],
        thumbprints: [stackConfig.github.oidcThumbprint],
      }
    );

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

    // Add inline policy for S3 + CloudFront permissions
    githubActionsRole.attachInlinePolicy(
      new iam.Policy(this, 'GithubActionsDeployPolicy', {
        statements: [
          new iam.PolicyStatement({
            actions: [
              's3:PutObject',
              's3:DeleteObject',
              's3:ListBucket',
            ],
            resources: [siteBucket.bucketArn, siteBucket.arnForObjects('*')],
          }),
          new iam.PolicyStatement({
            actions: ['cloudfront:CreateInvalidation'],
            resources: [
              `arn:aws:cloudfront::${cdk.Stack.of(this).account}:distribution/${
                distribution.distributionId
              }`,
            ],
          }),
        ],
      })
    );

    // Phase 1.5: Route53 DNS Records (requires hosted zone)
    // Note: Hosted zone lookup assumes it exists in the same AWS account
    if (stackConfig.hostedZoneId) {
      const hostedZone = route53.HostedZone.fromHostedZoneAttributes(
        this,
        'DctechEventsHostedZone',
        {
          hostedZoneId: stackConfig.hostedZoneId,
          zoneName: stackConfig.domain,
        }
      );

      // Create A record (IPv4)
      new route53.ARecord(this, 'DctechEventsARecord', {
        zone: hostedZone,
        target: route53.RecordTarget.fromAlias(
          new route53targets.CloudFrontTarget(distribution)
        ),
        recordName: stackConfig.domain,
      });

      // Create AAAA record (IPv6)
      new route53.AaaaRecord(this, 'DctechEventsAAAARecord', {
        zone: hostedZone,
        target: route53.RecordTarget.fromAlias(
          new route53targets.CloudFrontTarget(distribution)
        ),
        recordName: stackConfig.domain,
      });
    }

    // Phase 1.7: Stack outputs
    new cdk.CfnOutput(this, 'S3BucketName', {
      value: siteBucket.bucketName,
      description: 'S3 bucket name for static site',
      exportName: 'DctechEventsBucketName',
    });

    new cdk.CfnOutput(this, 'CloudFrontDistributionId', {
      value: distribution.distributionId,
      description: 'CloudFront distribution ID',
      exportName: 'DctechEventsDistributionId',
    });

    new cdk.CfnOutput(this, 'CloudFrontDomainName', {
      value: distribution.domainName,
      description: 'CloudFront domain name',
      exportName: 'DctechEventsCloudFrontDomain',
    });

    new cdk.CfnOutput(this, 'GithubActionsRoleArn', {
      value: githubActionsRole.roleArn,
      description: 'IAM role ARN for GitHub Actions',
      exportName: 'DctechEventsGithubActionsRoleArn',
    });

    // Apply tags to all resources
    cdk.Tags.of(this).add('project', stackConfig.tags.project);
    cdk.Tags.of(this).add('environment', stackConfig.tags.environment);
    cdk.Tags.of(this).add('managedBy', stackConfig.tags.managedBy);
  }
}
