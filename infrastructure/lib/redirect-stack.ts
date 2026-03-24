import * as cdk from 'aws-cdk-lib/core';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as route53targets from 'aws-cdk-lib/aws-route53-targets';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import { Construct } from 'constructs';
import { stackConfig } from './config';

export class RedirectStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    if (!stackConfig.redirectDomains) {
      return;
    }

    stackConfig.redirectDomains.forEach((config, index) => {
      const { domainName, hostedZoneId, alternateNames } = config;
      const allDomains = [domainName, ...(alternateNames || [])];

      // Look up the hosted zone
      const hostedZone = route53.HostedZone.fromHostedZoneAttributes(
        this,
        `RedirectHostedZone-${index}`,
        {
          hostedZoneId,
          zoneName: domainName,
        }
      );

      // Create SSL/TLS Certificate for the redirect domains
      const certificate = new acm.Certificate(this, `RedirectCertificate-${index}`, {
        domainName: domainName,
        subjectAlternativeNames: alternateNames,
        validation: acm.CertificateValidation.fromDns(hostedZone),
      });

      // S3 Bucket for redirection
      // Note: We don't use BucketWebsiteConfiguration because CloudFront + S3 Origin
      // is preferred for HTTPS redirects without public S3 access.
      // Actually, S3 website redirection is the simplest way to do 301/302.
      const redirectBucket = new s3.Bucket(this, `RedirectBucket-${index}`, {
        websiteRedirect: {
          hostName: stackConfig.domain,
          protocol: s3.RedirectProtocol.HTTPS,
        },
        removalPolicy: cdk.RemovalPolicy.DESTROY,
        autoDeleteObjects: true,
      });

      // CloudFront Distribution
      const distribution = new cloudfront.Distribution(this, `RedirectDistribution-${index}`, {
        defaultBehavior: {
          origin: new origins.S3StaticWebsiteOrigin(redirectBucket),
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        },
        domainNames: allDomains,
        certificate: certificate,
        comment: `Redirect from ${domainName} to ${stackConfig.domain}`,
      });

      // Route53 Records
      allDomains.forEach((domain, domainIndex) => {
        // Create A record (IPv4)
        new route53.ARecord(this, `RedirectARecord-${index}-${domainIndex}`, {
          zone: hostedZone,
          target: route53.RecordTarget.fromAlias(
            new route53targets.CloudFrontTarget(distribution)
          ),
          recordName: domain,
        });

        // Create AAAA record (IPv6)
        new route53.AaaaRecord(this, `RedirectAAAARecord-${index}-${domainIndex}`, {
          zone: hostedZone,
          target: route53.RecordTarget.fromAlias(
            new route53targets.CloudFrontTarget(distribution)
          ),
          recordName: domain,
        });
      });
    });
  }
}
