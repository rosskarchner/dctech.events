#!/usr/bin/env python3
import os

import aws_cdk as cdk

from dctechevents.placeholder import PlaceholderSite
from dctechevents.signup import SignUpStack
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
)

SignUpStack(
    app,
    "SignUpStack",
    userpool=userpoolstack.user_pool
)

app.synth()
