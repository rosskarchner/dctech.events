#!/usr/bin/env python3
import os

import aws_cdk as cdk

from dctechevents.website import WebsiteSite

from dctechevents.userpool import UserPoolStack

from dctechevents.api import ApiStack

from dctechevents.aggregator import AggregatorStack


app = cdk.App()
userpoolstack = UserPoolStack(
    app,
    "UserPoolStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
    ),
)

apistack = ApiStack(
    app,
    "ApiStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
    ),
    user_pool=userpoolstack.user_pool,
    user_pool_client=userpoolstack.client,
    user_pool_stack=userpoolstack,
    admin_group=userpoolstack.admin_group,
    editor_group=userpoolstack.editor_group
)





WebsiteSite(
    app,
    "WebsiteStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
    ),
    userpoolstack = userpoolstack,
    api_stack=apistack
)

aggregator = AggregatorStack(
    app,
    "AggregatorStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
    ),
    sources_table=apistack.sources_table,
    events_table=apistack.events_table
)

app.synth()
