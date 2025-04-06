import os
from aws_cdk import (
    Stack,
    Duration,
    aws_cognito as cognito,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_s3 as s3,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct

class UserPoolStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create an S3 bucket for verification codes with lifecycle policy
        self.verification_bucket = s3.Bucket(
            self, "VerificationCodesBucket",
            removal_policy=RemovalPolicy.DESTROY,  # For development; use RETAIN for production
            auto_delete_objects=True,  # For development; remove for production
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ExpireVerificationCodes",
                    expiration=Duration.days(1),  # Delete objects after 1 day
                    enabled=True
                )
            ],
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL
        )

        # Create Lambda functions for Cognito triggers
        define_auth_challenge_fn = lambda_.Function(
            self, "DefineAuthChallenge",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=lambda_.Code.from_asset("functions/define_auth_challenge")
        )

        create_auth_challenge_fn = lambda_.Function(
            self, "CreateAuthChallenge",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=lambda_.Code.from_asset("functions/create_auth_challenge"),
            environment={
                "BASE_URL": "https://dctech.events",
                "VERIFICATION_BUCKET_NAME": self.verification_bucket.bucket_name
            }
        )

        verify_auth_challenge_fn = lambda_.Function(
            self, "VerifyAuthChallenge",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=lambda_.Code.from_asset("functions/verify_auth_challenge"),
            environment={
                "VERIFICATION_BUCKET_NAME": self.verification_bucket.bucket_name
            }
        )

        # Grant S3 permissions to the Lambda functions
        self.verification_bucket.grant_read(verify_auth_challenge_fn)
        self.verification_bucket.grant_read_write(create_auth_challenge_fn)

        # Create the User Pool with Lambda triggers
        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            removal_policy=RemovalPolicy.RETAIN,
            self_sign_up_enabled=True,
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
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
                email_style=cognito.VerificationEmailStyle.CODE
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            lambda_triggers=cognito.UserPoolTriggers(
                define_auth_challenge=define_auth_challenge_fn,
                create_auth_challenge=create_auth_challenge_fn,
                verify_auth_challenge_response=verify_auth_challenge_fn
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

        # Create the client with custom auth enabled
        self.client = self.user_pool.add_client(
            "app-client",
            prevent_user_existence_errors=True,
            auth_flows=cognito.AuthFlow(
                admin_user_password=True,
                custom=True,
                user_password=True,
                user_srp=True
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(implicit_code_grant=True),
                scopes=[cognito.OAuthScope.EMAIL],
                callback_urls=["http://localhost:3000", "https://dctech.events/callback"],
                logout_urls=["http://localhost:3000", "https://dctech.events"],
            ),
            generate_secret=False,
        )
        
        # Outputs
        CfnOutput(self, "UserPoolId", value=self.user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=self.client.user_pool_client_id)
        CfnOutput(self, "VerificationBucketName", value=self.verification_bucket.bucket_name)
