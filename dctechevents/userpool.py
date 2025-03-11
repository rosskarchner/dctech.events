from aws_cdk import (
    Stack,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_certificatemanager as acm,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as apigwv2_integrations,
    aws_s3 as s3,
    aws_lambda as lambda_,
    aws_cognito as cognito,
    RemovalPolicy,
)
from constructs import Construct


class UserPoolStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            removal_policy=RemovalPolicy.RETAIN,
            self_sign_up_enabled=False,  # Disable self-signup for security
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
            )
        )

        self.domain = cognito.UserPoolDomain(
            self,
            "UserPoolDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"{self.stack_name.lower()}-userpool"
            ),
            user_pool=self.user_pool,
        )
