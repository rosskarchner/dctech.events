/**
 * Shared configuration across all sites
 */
export const sharedConfig = {
  // AWS region - CloudFront requires certificates in us-east-1
  region: 'us-east-1',

  // GitHub OIDC configuration (shared across all sites)
  github: {
    oidcProviderUrl: 'https://token.actions.githubusercontent.com',
    oidcClientId: 'sts.amazonaws.com',
    oidcThumbprint: '6938fd4d98bab03faadb97b34396831e3780aea1', // GitHub's OIDC thumbprint
    repositoryOwner: 'rosskarchner',
    repositoryName: 'dctech.events',
    ref: 'ref:refs/heads/main', // Only main branch
  },

  // IAM Role configuration (shared across all sites)
  iam: {
    roleName: 'GithubActionsDeployRole',
    sessionName: 'github-actions-deploy',
    sessionDuration: 3600, // 1 hour
  },

  // DynamoDB configuration (shared - single table for all sites)
  dynamodb: {
    tableName: 'DcTechEvents',
    billingMode: 'PAY_PER_REQUEST',
  },

  // Tags to apply to all resources
  tags: {
    project: 'dctech-events',
    environment: 'production',
    managedBy: 'CDK',
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
};

/**
 * DC Tech Events site configuration
 */
export const dctechSiteConfig = {
  // Stack metadata
  stackName: 'dctech-events',
  stackDescription: 'DC Tech Events - S3 + CloudFront + Route53 infrastructure',
  siteId: 'dctech',

  // Domain configuration
  domain: 'dctech.events',
  hostedZoneId: 'Z078066931R85FQDWCM3P',

  // Redirect configuration (specific to dctech.events)
  redirectDomains: [
    {
      domainName: 'dctechevents.com',
      hostedZoneId: 'Z01256093SBV195X5X4TH',
      alternateNames: ['www.dctechevents.com'],
    },
  ],

  // S3 bucket configuration
  s3: {
    bucketName: 'dctech-events-site-1768361440101',
    dataCacheBucketName: 'dctech-events-data-cache',
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

  // Cognito configuration
  cognito: {
    userPoolName: 'dctech-events-users',
    domainPrefix: 'dctech-events',
    customDomain: 'login.dctech.events',
    callbackUrls: [
      'https://dctech.events/edit/auth/callback.html',
      'https://www.dctech.events/edit/auth/callback.html',
      'http://localhost:5000/auth/callback',
    ],
    logoutUrls: [
      'https://dctech.events/edit/',
      'https://www.dctech.events/edit/',
      'http://localhost:5000/',
    ],
    ses: {
      fromEmail: 'noreply@dctech.events',
      fromName: 'DC Tech Events',
      replyTo: 'support@dctech.events',
    },
    verificationEmail: {
      subject: 'Verify your email for DC Tech Events',
      body: 'Welcome to DC Tech Events! Your verification code is {####}.',
    },
  },

  // Secrets Manager configuration
  secrets: {
    cognitoClientSecret: 'dctech-events/cognito-client-secret',
    microblogTokenSecret: 'dctech-events/microblog-token',
    githubTokenSecret: 'dctech-events/github-token',
  },

  // Newsletter configuration
  newsletter: {
    // 7 AM EST is 12 PM UTC (standard) or 11 AM UTC (daylight)
    // CRON format: (minute, hour, day-of-month, month, day-of-week)
    schedule: {
      minute: '0',
      hour: '12',
      day: 'MON',
    },
  },

  // Notification configuration
  notifications: {
    adminEmail: 'ross@karchner.com',
    // 8:30 AM EST is 13:30 PM UTC
    queueSchedule: {
      minute: '30',
      hour: '13',
    },
  },

  // Rebuild pipeline configuration
  rebuild: {
    queueName: 'dctech-events-rebuild.fifo',
    deduplicationWindowSeconds: 60,
    visibilityTimeoutSeconds: 900,
    lambdaTimeoutSeconds: 900,
    lambdaMemoryMB: 1024,
  },
};

/**
 * DC STEM Events site configuration
 * (New multi-site addition)
 */
export const dcstemSiteConfig = {
  // Stack metadata
  stackName: 'dcstem-events',
  stackDescription: 'DC STEM Events - S3 + CloudFront + Route53 infrastructure',
  siteId: 'dcstem',

  // Domain configuration
  domain: 'dc.localstem.events',
  hostedZoneId: '', // TODO: Replace with actual hosted zone ID for dc.localstem.events

  // No redirect domains for dcstem (can be added later if needed)
  redirectDomains: [],

  // S3 bucket configuration
  s3: {
    bucketName: 'dcstem-events-site-1768361440101',
    dataCacheBucketName: 'dcstem-events-data-cache',
    versioningEnabled: false,
    blockPublicAccess: true,
    encryption: true,
  },

  // CloudFront configuration (inherits from shared, can override)
  cloudfront: {
    minTTL: 0,
    defaultTTL: 86400,
    maxTTL: 31536000,
    httpVersion: 'http2and3',
    enableCompression: true,
    redirectHttpToHttps: true,
    // TODO: Provide WAF Web ACL ARN for dcstem (or create new one)
    webAclId: '',
  },

  // ACM Certificate configuration
  acm: {
    domainName: 'dc.localstem.events',
    alternativeNames: ['*.dc.localstem.events'],
    // Certificate is managed by CloudFormation
    existingCertificateArn: '',
  },

  // Cognito configuration (separate user pool for dcstem)
  cognito: {
    userPoolName: 'dcstem-events-users',
    domainPrefix: 'dcstem-events',
    customDomain: 'login.dc.localstem.events',
    callbackUrls: [
      'https://dc.localstem.events/edit/auth/callback.html',
      'https://www.dc.localstem.events/edit/auth/callback.html',
      'http://localhost:5001/auth/callback',
    ],
    logoutUrls: [
      'https://dc.localstem.events/edit/',
      'https://www.dc.localstem.events/edit/',
      'http://localhost:5001/',
    ],
    ses: {
      fromEmail: 'noreply@dc.localstem.events',
      fromName: 'DC STEM Events',
      replyTo: 'support@dc.localstem.events',
    },
    verificationEmail: {
      subject: 'Verify your email for DC STEM Events',
      body: 'Welcome to DC STEM Events! Your verification code is {####}.',
    },
  },

  // Secrets Manager configuration (separate secrets for dcstem)
  secrets: {
    cognitoClientSecret: 'dcstem-events/cognito-client-secret',
    microblogTokenSecret: 'dcstem-events/microblog-token',
    githubTokenSecret: 'dcstem-events/github-token',
  },

  // Newsletter configuration (shared schedule, can customize)
  newsletter: {
    schedule: {
      minute: '0',
      hour: '12',
      day: 'MON',
    },
  },

  // Notification configuration
  notifications: {
    adminEmail: 'ross@karchner.com',
    queueSchedule: {
      minute: '30',
      hour: '13',
    },
  },

  // Rebuild pipeline configuration (separate queue for dcstem)
  rebuild: {
    queueName: 'dcstem-events-rebuild.fifo',
    deduplicationWindowSeconds: 60,
    visibilityTimeoutSeconds: 900,
    lambdaTimeoutSeconds: 900,
    lambdaMemoryMB: 1024,
  },
};

/**
 * Sites configuration - maps site IDs to their configurations
 * This enables easy lookup and iteration across all sites
 */
export const sitesConfig = {
  dctech: dctechSiteConfig,
  dcstem: dcstemSiteConfig,
};

/**
 * Legacy stackConfig export for backward compatibility
 * Points to dctech configuration (the original/primary site) merged with shared config
 * This allows existing code to continue working without changes
 */
export const stackConfig = {
  ...sharedConfig,
  ...dctechSiteConfig,
};

/**
 * DC STEM Events site stack config (merged with shared config)
 */
export const dcstemStackConfig = {
  ...sharedConfig,
  ...dcstemSiteConfig,
};
