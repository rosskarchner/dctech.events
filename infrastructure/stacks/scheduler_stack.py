"""
Scheduler Stack for DC Tech Events - Calendar Refresh
"""
import os
from aws_cdk import (
    Stack,
    Duration,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_s3 as s3,
)
from constructs import Construct


class SchedulerStack(Stack):
    """Stack for scheduled calendar refresh Lambda"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        project_name: str,
        environment: str,
        events_table: dynamodb.Table,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # IAM role for event collection Lambda
        lambda_role = iam.Role(
            self,
            "EventCollectionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ],
        )

        # Grant DynamoDB write permissions
        events_table.grant_read_write_data(lambda_role)

        # Grant S3 read permissions (for groups definitions)
        # Reference the bucket from ApplicationStack
        assets_bucket_name = f"{project_name.lower()}-assets-{environment}"
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject", "s3:ListBucket"],
                resources=[
                    f"arn:aws:s3:::{assets_bucket_name}",
                    f"arn:aws:s3:::{assets_bucket_name}/*",
                ],
            )
        )

        # Event collection Lambda function
        self.event_collection_function = lambda_.Function(
            self,
            "EventCollectionFunction",
            function_name=f"{project_name}-EventCollection-{environment}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="refresh_calendars.lambda_handler",
            code=lambda_.Code.from_asset("../lambda/event-collection"),
            timeout=Duration.minutes(15),  # iCal fetching can take time
            memory_size=512,
            role=lambda_role,
            environment={
                "DYNAMODB_TABLE_NAME": events_table.table_name,
                "ASSETS_BUCKET": assets_bucket_name,
                "ENVIRONMENT": environment,
            },
        )

        # EventBridge rule - run daily at 2 AM UTC
        rule = events.Rule(
            self,
            "DailyRefreshRule",
            schedule=events.Schedule.cron(
                minute="0",
                hour="2",
                month="*",
                week_day="*",
                year="*"
            ),
            description="Daily calendar refresh for DC Tech Events",
        )

        # Add Lambda as target
        rule.add_target(targets.LambdaFunction(self.event_collection_function))

        # Manual invocation Lambda (for testing/manual refresh)
        self.manual_refresh_function = lambda_.Function(
            self,
            "ManualRefreshFunction",
            function_name=f"{project_name}-ManualRefresh-{environment}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_inline(
                """
import boto3
import os

lambda_client = boto3.client('lambda')

def handler(event, context):
    function_name = os.environ['EVENT_COLLECTION_FUNCTION']
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType='Event'  # Async invocation
    )
    return {
        'statusCode': 200,
        'body': 'Calendar refresh triggered'
    }
"""
            ),
            timeout=Duration.seconds(30),
            environment={
                "EVENT_COLLECTION_FUNCTION": self.event_collection_function.function_name,
            },
        )

        # Grant permission to invoke event collection function
        self.event_collection_function.grant_invoke(self.manual_refresh_function)
