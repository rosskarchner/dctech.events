// This file should be populated with CDK outputs after deployment
// Replace these placeholders with actual values from `cdk deploy` outputs

export const config = {
  // Cognito Configuration
  userPoolId: process.env.REACT_APP_USER_POOL_ID || 'YOUR_USER_POOL_ID',
  userPoolClientId: process.env.REACT_APP_USER_POOL_CLIENT_ID || 'YOUR_USER_POOL_CLIENT_ID',
  userPoolDomain: process.env.REACT_APP_USER_POOL_DOMAIN || 'organize-dctech-events',

  // API Configuration
  apiUrl: process.env.REACT_APP_API_URL || 'YOUR_API_URL',

  // App Configuration
  region: process.env.REACT_APP_REGION || 'us-east-1',
};

export default config;
