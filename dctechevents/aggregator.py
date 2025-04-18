from aws_cdk import (
    Stack,
    Duration,
    BundlingOptions,
    aws_lambda as lambda_,
    aws_events as events,
    aws_events_targets as targets,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_iam as iam,
    RemovalPolicy
)
from constructs import Construct


class AggregatorStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        groups_table: dynamodb.Table,
        events_table: dynamodb.Table,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        cache = s3.Bucket(
            self,
            "CacheBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # Create the Lambda function for processing iCal feeds
        aggregator_function = lambda_.Function(
            self,
            "AggregatorFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            code=lambda_.Code.from_asset("functions/aggregator"),
            handler="index.handler",
            timeout=Duration.minutes(5),
            memory_size=512,
            environment={
                "GROUPS_TABLE": groups_table.table_name,
                "EVENTS_TABLE": events_table.table_name,
                "TIMEZONE": "America/New_York",
                "CACHE_BUCKET": cache.bucket_name
            },
        )

        # Grant S3 permissions
        cache.grant_read_write(aggregator_function)

        # Grant DynamoDB permissions
        groups_table_ref = dynamodb.Table.from_table_name(
            self, "GroupsTable", groups_table.table_name
        )
        events_table_ref = dynamodb.Table.from_table_name(
            self, "EventsTable", events_table.table_name
        )

        groups_table_ref.grant_read_data(aggregator_function)
        events_table_ref.grant_read_write_data(aggregator_function)
        
        # Grant access to query the approval-status-index on the groups table
        # and the group-index on the events table
        aggregator_function.add_to_role_policy(iam.PolicyStatement(
            actions=['dynamodb:Query'],
            resources=[
                groups_table.table_arn + "/index/approval-status-index",
                events_table.table_arn + "/index/group-index",  # Updated to use group-index
                events_table.table_arn + "/index/*"  # This grants access to all indexes on events table
            ]
        ))

        # Create EventBridge rule to trigger the function
        events.Rule(
            self,
            "AggregatorSchedule",
            schedule=events.Schedule.rate(Duration.hours(1)),
            targets=[targets.LambdaFunction(aggregator_function)],
        )
