#!/usr/bin/env python3
import os

import aws_cdk as cdk

from dctechevents.certificates import CertificateStack
from dctechevents.website import WebsiteStack
from dctechevents.userpool import UserPoolStack
from dctechevents.api import ApiStack
from dctechevents.aggregator import AggregatorStack


app = cdk.App()

# Create the certificate stack first
cert_stack = CertificateStack(
    app,
    "CertificateStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
    ),
)

# Pass the certificate to the user pool stack
userpoolstack = UserPoolStack(
    app,
    "UserPoolStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
    ),
    certificate=cert_stack.certificate,
    hosted_zone=cert_stack.hosted_zone,
)

# Pass the certificate to the website stack
websitestack = WebsiteStack(
    app,
    "WebsiteStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
    ),
    certificate=cert_stack.certificate,
    hosted_zone=cert_stack.hosted_zone,
)

# Pass the certificate to the API stack
apistack = ApiStack(
    app,
    "ApiStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
    ),
    rendered_site_bucket=websitestack.rendered_site_bucket,
    user_pool=userpoolstack.user_pool,
    user_pool_client=userpoolstack.client,
    user_pool_stack=userpoolstack,
    admin_group=userpoolstack.admin_group,
    editor_group=userpoolstack.editor_group,
    certificate=cert_stack.certificate,
    hosted_zone=cert_stack.hosted_zone,
    distribution=websitestack.distribution,
)

aggregator = AggregatorStack(
    app,
    "AggregatorStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
    ),
    groups_table=apistack.groups_table,
    events_table=apistack.events_table
)


app.synth()
