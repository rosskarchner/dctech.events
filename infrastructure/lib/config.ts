/**
 * Stack configuration for DC Tech Events infrastructure
 */
export const stackConfig = {
  // Stack metadata
  stackName: 'dctech-events',
  stackDescription: 'DC Tech Events - S3 + CloudFront + Route53 infrastructure',

  // Domain configuration
  domain: 'dctech.events',
  hostedZoneId: 'Z078066931R85FQDWCM3P',

  // AWS region - CloudFront requires certificates in us-east-1
  region: 'us-east-1',

  // S3 bucket configuration
  s3: {
    bucketName: 'dctech-events-site-1768361440101',
    dataCacheBucketName: 'dctech-events-data-cache',
    versioningEnabled: false,
    blockPublicAccess: true,
    encryption: true,
  },

  // DynamoDB configuration
  dynamodb: {
    tableName: 'DcTechEvents',
    billingMode: 'PAY_PER_REQUEST',
  },

  // CloudFront configuration
  cloudfront: {
    minTTL: 0,
    defaultTTL: 86400, // 1 day
    maxTTL: 31536000, // 1 year
    httpVersion: 'http2and3',
    enableCompression: true,
    redirectHttpToHttps: true,
    // Web ACL from CloudFront pricing plan subscription - must be preserved in updates
    webAclId: 'arn:aws:wafv2:us-east-1:797438674243:global/webacl/CreatedByCloudFront-bc55731a/1e530f09-09ff-4259-a51f-81c7a4aeb9fb',
  },

  // ACM Certificate configuration
  acm: {
    domainName: 'dctech.events',
    alternativeNames: ['*.dctech.events'],
    // Certificate is managed by CloudFormation
    existingCertificateArn: '',
  },

  // GitHub OIDC configuration
  github: {
    oidcProviderUrl: 'https://token.actions.githubusercontent.com',
    oidcClientId: 'sts.amazonaws.com',
    oidcThumbprint: '6938fd4d98bab03faadb97b34396831e3780aea1', // GitHub's OIDC thumbprint
    repositoryOwner: 'rosskarchner',
    repositoryName: 'dctech.events',
    ref: 'ref:refs/heads/main', // Only main branch
  },

  // IAM Role configuration
  iam: {
    roleName: 'GithubActionsDeployRole',
    sessionName: 'github-actions-deploy',
    sessionDuration: 3600, // 1 hour
  },

  // Cognito configuration
  cognito: {
    userPoolName: 'dctech-events-users',
    domainPrefix: 'dctech-events',
    customDomain: 'login.dctech.events',
    callbackUrls: [
      'https://suggest.dctech.events/auth/callback',
      'https://manage.dctech.events/auth/callback',
      'http://localhost:5000/auth/callback',
    ],
    logoutUrls: [
      'https://suggest.dctech.events/',
      'https://manage.dctech.events/',
      'http://localhost:5000/',
    ],
  },

  // Secrets Manager configuration
  secrets: {
    cognitoClientSecret: 'dctech-events/cognito-client-secret',
  },

  // Chalice API configuration (legacy, used by lambda-api-stack)
  chalice: {
    mainApi: {
      stageName: 'prod',
    },
  },

  // Feature flags
  features: {
    enableCustomDomain: true,
  },

  // Rebuild pipeline configuration
  rebuild: {
    queueName: 'dctech-events-rebuild.fifo',
    deduplicationWindowSeconds: 60,
    visibilityTimeoutSeconds: 900,
    lambdaTimeoutSeconds: 900,
    lambdaMemoryMB: 2048,
  },

  // Tags to apply to all resources
  tags: {
    project: 'dctech-events',
    environment: 'production',
    managedBy: 'CDK',
  },
};
