/**
 * Stack configuration for DC Tech Events infrastructure
 */
export const stackConfig = {
  // Stack metadata
  stackName: 'dctech-events',
  stackDescription: 'DC Tech Events - S3 + CloudFront + Route53 infrastructure',

  // Domain configuration
  domain: 'dctech.events',
  hostedZoneId: process.env.HOSTED_ZONE_ID || '', // Must be set via environment variable

  // AWS region - CloudFront requires certificates in us-east-1
  region: 'us-east-1',

  // S3 bucket configuration
  s3: {
    bucketName: `dctech-events-site-${Date.now()}`, // Use timestamp to ensure uniqueness
    versioningEnabled: false,
    blockPublicAccess: true,
    encryption: true,
  },

  // CloudFront configuration
  cloudfront: {
    minTTL: 0,
    defaultTTL: 86400, // 1 day
    maxTTL: 31536000, // 1 year
    httpVersion: 'http2and3',
    enableCompression: true,
    redirectHttpToHttps: true,
  },

  // ACM Certificate configuration
  acm: {
    domainName: 'dctech.events',
    alternativeNames: ['*.dctech.events'],
    // Set to use existing certificate ARN if available
    existingCertificateArn: process.env.ACM_CERTIFICATE_ARN || '',
  },

  // GitHub OIDC configuration
  github: {
    oidcProviderUrl: 'https://token.actions.githubusercontent.com',
    oidcClientId: 'sts.amazonaws.com',
    oidcThumbprint: '6938fd4d98bab03faadb97b34396831e3780aea1', // GitHub's OIDC thumbprint
    repositoryOwner: 'dctech-community',
    repositoryName: 'dctech.events',
    ref: 'ref:refs/heads/main', // Only main branch
  },

  // IAM Role configuration
  iam: {
    roleName: 'GithubActionsDeployRole',
    sessionName: 'github-actions-deploy',
    sessionDuration: 3600, // 1 hour
  },

  // Tags to apply to all resources
  tags: {
    project: 'dctech-events',
    environment: 'production',
    managedBy: 'CDK',
  },
};
