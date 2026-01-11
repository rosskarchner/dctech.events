#!/usr/bin/env python3
"""
CDK App for DC Tech Events Infrastructure
"""
import os
from aws_cdk import App, Environment, Tags

from stacks.database_stack import DatabaseStack
from stacks.application_stack import ApplicationStack
from stacks.distribution_stack import DistributionStack
from stacks.scheduler_stack import SchedulerStack

app = App()

# Get environment configuration
account = os.getenv('CDK_DEFAULT_ACCOUNT')
region = os.getenv('CDK_DEFAULT_REGION', 'us-east-1')

env = Environment(account=account, region=region)

# Stack naming
project_name = "DCTechEvents"
environment_name = app.node.try_get_context("environment") or "prod"

# Database Stack - DynamoDB tables (Events + Groups)
database_stack = DatabaseStack(
    app,
    f"{project_name}-Database-{environment_name}",
    project_name=project_name,
    environment=environment_name,
    env=env,
    description="DynamoDB tables for DC Tech Events (Events + Groups)"
)

# Application Stack - Chalice app, Lambda, API Gateway
application_stack = ApplicationStack(
    app,
    f"{project_name}-Application-{environment_name}",
    project_name=project_name,
    environment=environment_name,
    events_table=database_stack.events_table,
    groups_table=database_stack.groups_table,
    env=env,
    description="Chalice API application for DC Tech Events"
)

# Scheduler Stack - EventBridge rules for calendar refresh
scheduler_stack = SchedulerStack(
    app,
    f"{project_name}-Scheduler-{environment_name}",
    project_name=project_name,
    environment=environment_name,
    events_table=database_stack.events_table,
    groups_table=database_stack.groups_table,
    env=env,
    description="Scheduled event collection for DC Tech Events"
)

# Distribution Stack - CloudFront CDN
distribution_stack = DistributionStack(
    app,
    f"{project_name}-Distribution-{environment_name}",
    project_name=project_name,
    environment=environment_name,
    api_domain=application_stack.api_url,
    env=env,
    description="CloudFront distribution for DC Tech Events"
)

# Add common tags
Tags.of(app).add("Project", project_name)
Tags.of(app).add("Environment", environment_name)
Tags.of(app).add("ManagedBy", "CDK")

app.synth()
