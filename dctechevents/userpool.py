import os
from aws_cdk import (
    Stack,
    Duration,
    aws_cognito as cognito,
    aws_iam as iam,
    aws_s3 as s3,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_certificatemanager as acm,
    RemovalPolicy,
    CfnOutput,
    CustomResource,
    custom_resources as cr,
    aws_lambda as lambda_,
)
from constructs import Construct

class UserPoolStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, certificate, hosted_zone, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create the User Pool with simplified configuration
        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            removal_policy=RemovalPolicy.RETAIN,
            self_sign_up_enabled=True,
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
                given_name=cognito.StandardAttribute(required=True, mutable=True),
                family_name=cognito.StandardAttribute(required=True, mutable=True),
            ),
            custom_attributes={
                "newsletter": cognito.BooleanAttribute(
                    mutable=True,
                ),
                "nickname": cognito.StringAttribute(
                    min_len=1,
                    max_len=100,
                    mutable=True
                ),
                "website": cognito.StringAttribute(
                    min_len=0,
                    max_len=2048,
                    mutable=True
                ),
                "profile_complete": cognito.BooleanAttribute(
                    mutable=True
                )
            },
            sign_in_aliases=cognito.SignInAliases(
                email=True,
                username=False,
                phone=False,
            ),
            sign_in_case_sensitive=False,
            user_verification=cognito.UserVerificationConfig(
                email_style=cognito.VerificationEmailStyle.LINK
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            auto_verify={"email": True},
        )

        # Create groups
        self.admin_group = cognito.CfnUserPoolGroup(
            self,
            "AdminGroup",
            user_pool_id=self.user_pool.user_pool_id,
            group_name="admins",
            precedence=0
        )

        self.editor_group = cognito.CfnUserPoolGroup(
            self,
            "EditorGroup",
            user_pool_id=self.user_pool.user_pool_id,
            group_name="editors",
            precedence=1
        )

        # Create the custom domain for the hosted UI
        domain = self.user_pool.add_domain(
            "CognitoCustomDomain",
            custom_domain=cognito.CustomDomainOptions(
                domain_name="auth.dctech.events",
                certificate=certificate
            ),
        )

        # Create DNS records for the Cognito domain
        route53.ARecord(
            self, "AuthARecord",
            zone=hosted_zone,
            record_name="auth",
            target=route53.RecordTarget.from_alias(
                targets.UserPoolDomainTarget(domain)
            )
        )

        route53.AaaaRecord(
            self, "AuthAAAARecord",
            zone=hosted_zone,
            record_name="auth",
            target=route53.RecordTarget.from_alias(
                targets.UserPoolDomainTarget(domain)
            )
        )

        # Create the client with OAuth settings for hosted UI with modern UI
        self.client = self.user_pool.add_client(
            "app-client",
            prevent_user_existence_errors=True,
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True,
                    implicit_code_grant=True
                ),
                scopes=[
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.PROFILE
                ],
                callback_urls=[
                    "https://dctech.events/static/callback.html",
                    "https://www.dctech.events/static/callback.html",
                    "http://localhost:3000/static/callback.html"  # For local development
                ],
                logout_urls=[
                    "https://dctech.events/static/logout.html",
                    "https://www.dctech.events/static/logout.html",
                    "http://localhost:3000/static/logout.html"  # For local development
                ],
            ),
            generate_secret=False,
            user_pool_client_name="DC Tech Events App",
        )