import * as cdk from 'aws-cdk-lib/core';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import { stackConfig } from './config';
import * as path from 'path';

export interface SocialPostingStackProps extends cdk.StackProps {
  microblogTokenSecretArn: string;
  materializedTableArn: string;
}

export class SocialPostingStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: SocialPostingStackProps) {
    super(scope, id, props);

    // Common bundling options for social posting lambdas
    const bundlingOptions = {
      image: lambda.Runtime.PYTHON_3_12.bundlingImage,
      command: [
        'bash', '-c',
        'pip install -r lambdas/newsletter_post/requirements.txt -t /asset-output && cp -r lambdas/* /asset-output/ && cp config.yaml /asset-output/ && cp db_utils.py /asset-output/',
      ],
    };

    const commonEnv = {
      MB_TOKEN_SECRET_NAME: stackConfig.secrets.microblogTokenSecret,
    };

    // 1. Weekly Newsletter Lambda (Monday 7 AM EST)
    const newsletterFn = new lambda.Function(this, 'WeeklyNewsletterFunction', {
      functionName: 'dctech-events-weekly-newsletter',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'newsletter_post/handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../'), {
        exclude: ['.git', 'node_modules', '.beads', '.venv', 'infrastructure', 'build', 'static', '_cache', '_data', '__pycache__'],
        bundling: bundlingOptions,
      }),
      timeout: cdk.Duration.seconds(60),
      environment: commonEnv,
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // 2. Daily Event Summary Lambda (8 AM EST daily)
    const dailySummaryFn = new lambda.Function(this, 'DailySummaryFunction', {
      functionName: 'dctech-events-daily-summary',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'daily_summary/handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../'), {
        exclude: ['.git', 'node_modules', '.beads', '.venv', 'infrastructure', 'build', 'static', '_cache', '_data', '__pycache__'],
        bundling: bundlingOptions,
      }),
      timeout: cdk.Duration.seconds(60),
      environment: commonEnv,
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // 3. New Events Summary Lambda (9:30 PM EST daily)
    const newEventsSummaryFn = new lambda.Function(this, 'NewEventsSummaryFunction', {
      functionName: 'dctech-events-new-events-summary',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'new_events_summary/handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../'), {
        exclude: ['.git', 'node_modules', '.beads', '.venv', 'infrastructure', 'build', 'static', '_cache', '_data', '__pycache__'],
        bundling: bundlingOptions,
      }),
      timeout: cdk.Duration.seconds(60),
      environment: commonEnv,
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // Grant permissions
    [newsletterFn, dailySummaryFn, newEventsSummaryFn].forEach(fn => {
      // Secret access
      fn.addToRolePolicy(new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['secretsmanager:GetSecretValue'],
        resources: [props.microblogTokenSecretArn],
      }));
      
      // DynamoDB access (Materialized table DcTechEvents)
      fn.addToRolePolicy(new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['dynamodb:Query', 'dynamodb:Scan', 'dynamodb:GetItem'],
        resources: [props.materializedTableArn, `${props.materializedTableArn}/index/*`],
      }));
    });

    // Schedules (All times are UTC)
    // 7 AM EST is 12:00 PM UTC
    new events.Rule(this, 'NewsletterScheduleRule', {
      schedule: events.Schedule.expression('cron(0 12 ? * MON *)'),
      targets: [new targets.LambdaFunction(newsletterFn)],
      description: 'Trigger weekly newsletter post to Micro.blog (Mon 7 AM EST)',
    });

    // 8 AM EST is 13:00 PM UTC
    new events.Rule(this, 'DailySummaryScheduleRule', {
      schedule: events.Schedule.expression('cron(0 13 * * ? *)'),
      targets: [new targets.LambdaFunction(dailySummaryFn)],
      description: 'Trigger daily event summary post to Micro.blog (Daily 8 AM EST)',
    });

    // 9:30 PM EST is 02:30 AM UTC (next day)
    new events.Rule(this, 'NewEventsSummaryScheduleRule', {
      schedule: events.Schedule.expression('cron(30 2 * * ? *)'),
      targets: [new targets.LambdaFunction(newEventsSummaryFn)],
      description: 'Trigger daily new events summary post to Micro.blog (Daily 9:30 PM EST)',
    });

    // Apply tags
    cdk.Tags.of(this).add('project', stackConfig.tags.project);
    cdk.Tags.of(this).add('managedBy', stackConfig.tags.managedBy);
  }
}
