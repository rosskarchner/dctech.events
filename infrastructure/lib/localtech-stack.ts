import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as targets from 'aws-cdk-lib/aws-route53-targets';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as fs from 'fs';
import * as path from 'path';

export class LocalTechStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Domain configuration
    const domainName = 'localtech.events';
    const wildcardDomain = `*.${domainName}`;

    // S3 Bucket for hosting static content
    const hostingBucket = new s3.Bucket(this, 'LocalTechHostingBucket', {
      bucketName: 'localtech-events-hosting',
      websiteIndexDocument: 'index.html',
      websiteErrorDocument: '404.html',
      publicReadAccess: false,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      autoDeleteObjects: false,
      versioned: false,
      encryption: s3.BucketEncryption.S3_MANAGED,
    });

    // Origin Access Control for CloudFront
    const oac = new cloudfront.S3OriginAccessControl(this, 'OAC', {
      signing: cloudfront.Signing.SIGV4_NO_OVERRIDE,
    });

    // CloudFront Function for subdomain routing
    // This function routes requests from subdomains to the correct S3 prefix
    const routingFunctionCode = fs.readFileSync(
      path.join(__dirname, 'origin-request-function.js'),
      'utf-8'
    );

    const routingFunction = new cloudfront.Function(this, 'RoutingFunction', {
      functionName: 'localtech-subdomain-routing',
      code: cloudfront.FunctionCode.fromInline(routingFunctionCode),
      comment: 'Routes subdomain requests to city-specific S3 prefixes',
      runtime: cloudfront.FunctionRuntime.JS_2_0,
    });

    // Look up the hosted zone (must already exist)
    const hostedZone = route53.HostedZone.fromLookup(this, 'HostedZone', {
      domainName: domainName,
    });

    // ACM Certificate for apex and wildcard domain
    const certificate = new acm.Certificate(this, 'Certificate', {
      domainName: domainName,
      subjectAlternativeNames: [wildcardDomain],
      validation: acm.CertificateValidation.fromDns(hostedZone),
    });

    // CloudFront Distribution
    const distribution = new cloudfront.Distribution(this, 'Distribution', {
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(hostingBucket, {
          originAccessControl: oac,
        }),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        functionAssociations: [
          {
            function: routingFunction,
            eventType: cloudfront.FunctionEventType.VIEWER_REQUEST,
          },
        ],
      },
      domainNames: [domainName, wildcardDomain],
      certificate: certificate,
      defaultRootObject: 'index.html',
      errorResponses: [
        {
          httpStatus: 404,
          responseHttpStatus: 404,
          responsePagePath: '/404.html',
          ttl: cdk.Duration.minutes(5),
        },
        {
          httpStatus: 403,
          responseHttpStatus: 404,
          responsePagePath: '/404.html',
          ttl: cdk.Duration.minutes(5),
        },
      ],
      priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
      comment: 'LocalTech Events multi-city distribution',
    });

    // Allow CloudFront to read from S3
    hostingBucket.addToResourcePolicy(
      new iam.PolicyStatement({
        actions: ['s3:GetObject'],
        resources: [hostingBucket.arnForObjects('*')],
        principals: [new iam.ServicePrincipal('cloudfront.amazonaws.com')],
        conditions: {
          StringEquals: {
            'AWS:SourceArn': `arn:aws:cloudfront::${this.account}:distribution/${distribution.distributionId}`,
          },
        },
      })
    );

    // Route53 A record for apex domain
    new route53.ARecord(this, 'ApexARecord', {
      zone: hostedZone,
      recordName: domainName,
      target: route53.RecordTarget.fromAlias(
        new targets.CloudFrontTarget(distribution)
      ),
    });

    // Route53 AAAA record for apex domain (IPv6)
    new route53.AaaaRecord(this, 'ApexAAAARecord', {
      zone: hostedZone,
      recordName: domainName,
      target: route53.RecordTarget.fromAlias(
        new targets.CloudFrontTarget(distribution)
      ),
    });

    // Route53 A record for wildcard subdomain
    new route53.ARecord(this, 'WildcardARecord', {
      zone: hostedZone,
      recordName: wildcardDomain,
      target: route53.RecordTarget.fromAlias(
        new targets.CloudFrontTarget(distribution)
      ),
    });

    // Route53 AAAA record for wildcard subdomain (IPv6)
    new route53.AaaaRecord(this, 'WildcardAAAARecord', {
      zone: hostedZone,
      recordName: wildcardDomain,
      target: route53.RecordTarget.fromAlias(
        new targets.CloudFrontTarget(distribution)
      ),
    });

    // IAM User for GitHub Actions deployment (unified for both static site and OAuth endpoint)
    const deploymentUser = new iam.User(this, 'DeploymentUser', {
      userName: 'localtech-github-actions-deployer',
    });

    // IAM Policy for deployment permissions
    const deploymentPolicy = new iam.ManagedPolicy(this, 'DeploymentPolicy', {
      managedPolicyName: 'LocalTechDeploymentPolicy',
      description: 'Permissions for GitHub Actions to deploy LocalTech Events (static site + OAuth endpoint)',
      statements: [
        // ============================================
        // Static Site Deployment Permissions
        // ============================================

        // S3 Bucket permissions
        new iam.PolicyStatement({
          sid: 'S3BucketAccess',
          effect: iam.Effect.ALLOW,
          actions: [
            's3:ListBucket',
            's3:GetBucketLocation',
          ],
          resources: [hostingBucket.bucketArn],
        }),
        // S3 Object permissions
        new iam.PolicyStatement({
          sid: 'S3ObjectAccess',
          effect: iam.Effect.ALLOW,
          actions: [
            's3:PutObject',
            's3:GetObject',
            's3:DeleteObject',
          ],
          resources: [hostingBucket.arnForObjects('*')],
        }),
        // CloudFront invalidation permissions
        new iam.PolicyStatement({
          sid: 'CloudFrontInvalidation',
          effect: iam.Effect.ALLOW,
          actions: [
            'cloudfront:CreateInvalidation',
            'cloudfront:GetInvalidation',
            'cloudfront:ListInvalidations',
          ],
          resources: [
            `arn:aws:cloudfront::${this.account}:distribution/${distribution.distributionId}`,
          ],
        }),

        // ============================================
        // OAuth Endpoint (Chalice) Deployment Permissions
        // ============================================

        // Lambda function management
        new iam.PolicyStatement({
          sid: 'LambdaFunctionManagement',
          effect: iam.Effect.ALLOW,
          actions: [
            'lambda:CreateFunction',
            'lambda:UpdateFunctionCode',
            'lambda:UpdateFunctionConfiguration',
            'lambda:GetFunction',
            'lambda:GetFunctionConfiguration',
            'lambda:DeleteFunction',
            'lambda:AddPermission',
            'lambda:RemovePermission',
            'lambda:ListVersionsByFunction',
            'lambda:PublishVersion',
            'lambda:GetPolicy',
            'lambda:ListTags',
            'lambda:TagResource',
            'lambda:UntagResource',
            'lambda:DeleteFunctionConcurrency',
            'lambda:PutFunctionConcurrency',
          ],
          resources: [`arn:aws:lambda:us-east-1:${this.account}:function:dctech-events-submit-*`],
        }),

        // API Gateway management
        new iam.PolicyStatement({
          sid: 'APIGatewayManagement',
          effect: iam.Effect.ALLOW,
          actions: [
            'apigateway:GET',
            'apigateway:POST',
            'apigateway:PUT',
            'apigateway:DELETE',
            'apigateway:PATCH',
          ],
          // NOTE: The following permissions grant access to all REST APIs in the account.
          // This is broader than necessary and violates the principle of least privilege.
          // After the first deployment, replace the wildcard with the specific API ID:
          //   const apiId = '<YOUR_API_ID>';
          //   resources: [
          //     `arn:aws:apigateway:us-east-1::/restapis/${apiId}`,
          //     `arn:aws:apigateway:us-east-1::/restapis/${apiId}/*`,
          //   ],
          // For initial deployment, the wildcard is used. Update after API creation.
          resources: [
            `arn:aws:apigateway:us-east-1::/restapis`,
            `arn:aws:apigateway:us-east-1::/restapis/*`,
          ],

        // IAM role management (for Lambda execution role)
        new iam.PolicyStatement({
          sid: 'IAMRoleManagement',
          effect: iam.Effect.ALLOW,
          actions: [
            'iam:CreateRole',
            'iam:DeleteRole',
            'iam:PutRolePolicy',
            'iam:DeleteRolePolicy',
            'iam:GetRole',
            'iam:GetRolePolicy',
            'iam:PassRole',
            'iam:AttachRolePolicy',
            'iam:DetachRolePolicy',
            'iam:ListRolePolicies',
            'iam:ListAttachedRolePolicies',
          ],
          resources: [
            `arn:aws:iam::${this.account}:role/dctech-events-submit-*`,
          ],
        }),

        // Secrets Manager read access
        new iam.PolicyStatement({
          sid: 'SecretsManagerRead',
          effect: iam.Effect.ALLOW,
          actions: [
            'secretsmanager:GetSecretValue',
            'secretsmanager:DescribeSecret',
          ],
          resources: [`arn:aws:secretsmanager:us-east-1:${this.account}:secret:dctech-events/*`],
        }),

        // CloudFormation stack management (Chalice uses CloudFormation)
        new iam.PolicyStatement({
          sid: 'CloudFormationStackManagement',
          effect: iam.Effect.ALLOW,
          actions: [
            'cloudformation:CreateStack',
            'cloudformation:UpdateStack',
            'cloudformation:DeleteStack',
            'cloudformation:DescribeStacks',
            'cloudformation:DescribeStackEvents',
            'cloudformation:DescribeStackResource',
            'cloudformation:DescribeStackResources',
            'cloudformation:GetTemplate',
            'cloudformation:ValidateTemplate',
          ],
          resources: [`arn:aws:cloudformation:us-east-1:${this.account}:stack/dctech-events-submit-*/*`],
        }),

        // CloudWatch Logs access
        new iam.PolicyStatement({
          sid: 'CloudWatchLogsAccess',
          effect: iam.Effect.ALLOW,
          actions: [
            'logs:DescribeLogGroups',
            'logs:DescribeLogStreams',
            'logs:FilterLogEvents',
          ],
          resources: [`arn:aws:logs:us-east-1:${this.account}:log-group:/aws/lambda/dctech-events-submit-*`],
        }),
      ],
    });

    // Attach policy to user
    deploymentUser.addManagedPolicy(deploymentPolicy);

    // Outputs
    new cdk.CfnOutput(this, 'BucketName', {
      value: hostingBucket.bucketName,
      description: 'S3 bucket name for hosting',
      exportName: 'LocalTechBucketName',
    });

    new cdk.CfnOutput(this, 'DistributionId', {
      value: distribution.distributionId,
      description: 'CloudFront distribution ID',
      exportName: 'LocalTechDistributionId',
    });

    new cdk.CfnOutput(this, 'DistributionDomain', {
      value: distribution.distributionDomainName,
      description: 'CloudFront distribution domain name',
      exportName: 'LocalTechDistributionDomain',
    });

    new cdk.CfnOutput(this, 'ApexDomain', {
      value: `https://${domainName}`,
      description: 'Apex domain URL',
    });

    new cdk.CfnOutput(this, 'DeploymentUserName', {
      value: deploymentUser.userName,
      description: 'IAM user for GitHub Actions deployment',
      exportName: 'LocalTechDeploymentUserName',
    });

    new cdk.CfnOutput(this, 'DeploymentUserArn', {
      value: deploymentUser.userArn,
      description: 'IAM user ARN',
    });
  }
}
