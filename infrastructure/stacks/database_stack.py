"""
DynamoDB Database Stack for DC Tech Events
Enhanced with approval workflow for events and groups
"""
from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
)
from constructs import Construct


class DatabaseStack(Stack):
    """Stack for DynamoDB tables - Events and Groups"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        project_name: str,
        environment: str,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Events Table (with approval workflow)
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
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,  # For notifications
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

        # GSI 4: Query by status (for admin approval workflow)
        self.events_table.add_global_secondary_index(
            index_name="StatusIndex",
            partition_key=dynamodb.Attribute(
                name="status",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="submitted_at",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        # Groups Table - replaces _groups/*.yaml files
        self.groups_table = dynamodb.Table(
            self,
            "GroupsTable",
            table_name=f"{project_name}-Groups-{environment}",
            partition_key=dynamodb.Attribute(
                name="group_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            point_in_time_recovery=True,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
        )

        # Groups GSI 1: Query by status (for admin approval)
        self.groups_table.add_global_secondary_index(
            index_name="StatusIndex",
            partition_key=dynamodb.Attribute(
                name="status",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="submitted_at",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        # Groups GSI 2: Query active+approved groups (for event collection)
        self.groups_table.add_global_secondary_index(
            index_name="ActiveApprovedIndex",
            partition_key=dynamodb.Attribute(
                name="active_approved",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="name",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        # Output table names
        self.events_table_name = self.events_table.table_name
        self.groups_table_name = self.groups_table.table_name
