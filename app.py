#!/usr/bin/env python3
import os

import aws_cdk as cdk

from dctechevents.placeholder import PlaceholderSite

from dctechevents.userpool import UserPoolStack


app = cdk.App()
PlaceholderSite(
    app,
    "PlaceholderStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
    ),
)

userpoolstack = UserPoolStack(
    app,
    "UserPoolStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
    ),
)



app.synth()
