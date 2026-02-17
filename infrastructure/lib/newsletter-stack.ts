import * as cdk from 'aws-cdk-lib/core';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import { stackConfig } from './config';
import * as path from 'path';

export interface NewsletterStackProps extends cdk.StackProps {
  microblogTokenSecretArn: string;
}

export class NewsletterStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: NewsletterStackProps) {
    super(scope, id, props);

    // Lambda function to post the newsletter
    // Using a Docker-based approach or standard Lambda with bundling
    const newsletterFn = new lambda.Function(this, 'NewsletterPostFunction', {
      functionName: 'dctech-events-newsletter-post',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../'), {
        exclude: [
          '.git',
          'node_modules',
          '.beads',
          '.venv',
          'infrastructure',
          'build',
          'static',
          '_cache',
          '_data',
          '__pycache__',
        ],
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -r lambdas/newsletter_post/requirements.txt -t /asset-output && cp lambdas/newsletter_post/handler.py /asset-output/ && cp config.yaml /asset-output/',
          ],
        },
      }),
      timeout: cdk.Duration.seconds(60),
      environment: {
        MB_TOKEN_SECRET_NAME: stackConfig.secrets.microblogTokenSecret,
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // Grant permission to read the secret
    newsletterFn.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['secretsmanager:GetSecretValue'],
      resources: [props.microblogTokenSecretArn],
    }));

    // Schedule the Lambda to run on Monday mornings
    // 12:00 PM UTC = 7:00 AM EST (standard)
    const rule = new events.Rule(this, 'NewsletterScheduleRule', {
      schedule: events.Schedule.expression('cron(0 12 ? * MON *)'),
      description: 'Trigger weekly newsletter post to Micro.blog',
    });

    rule.addTarget(new targets.LambdaFunction(newsletterFn));

    // Apply tags
    cdk.Tags.of(this).add('project', stackConfig.tags.project);
    cdk.Tags.of(this).add('managedBy', stackConfig.tags.managedBy);
  }
}
