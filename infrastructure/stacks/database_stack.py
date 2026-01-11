"""
DynamoDB Database Stack for DC Tech Events
"""
from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
)
from constructs import Construct


class DatabaseStack(Stack):
    """Stack for DynamoDB tables"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        project_name: str,
        environment: str,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Events Table
        self.events_table = dynamodb.Table(
            self,
            "EventsTable",
            table_name=f"{project_name}-Events-{environment}",
            partition_key=dynamodb.Attribute(
                name="event_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="start_datetime",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            removal_policy=RemovalPolicy.RETAIN,  # Protect production data
            point_in_time_recovery=True,  # Enable backups
        )

        # GSI 1: Query events by state and date (for upcoming events page)
        self.events_table.add_global_secondary_index(
            index_name="DateIndex",
            partition_key=dynamodb.Attribute(
                name="state",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="start_datetime",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        # GSI 2: Query events by group (for group-specific pages)
        self.events_table.add_global_secondary_index(
            index_name="GroupIndex",
            partition_key=dynamodb.Attribute(
                name="group_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="start_datetime",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        # GSI 3: Query by location_type (virtual vs in-person)
        self.events_table.add_global_secondary_index(
            index_name="LocationTypeIndex",
            partition_key=dynamodb.Attribute(
                name="location_type",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="start_datetime",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        # Output table name
        self.table_name = self.events_table.table_name
