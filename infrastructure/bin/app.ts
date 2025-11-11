#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { LocalTechStack } from '../lib/localtech-stack';

const app = new cdk.App();

new LocalTechStack(app, 'LocalTechEventsStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: 'us-east-1', // CloudFront requires ACM certificates in us-east-1
  },
  description: 'LocalTech Events multi-city platform infrastructure',
});

app.synth();
