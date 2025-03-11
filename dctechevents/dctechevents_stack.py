from aws_cdk import (
    # Duration,
    Stack,
    aws_route53 as route53
    # aws_sqs as sqs,
)
from constructs import Construct

class DctecheventsStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        