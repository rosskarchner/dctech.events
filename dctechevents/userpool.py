import os
from aws_cdk import (
    Stack,
    aws_cognito as cognito,
    aws_lambda as lambda_,
    aws_iam as iam,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct

class UserPoolStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # First, create all Lambda functions
        pre_signup_fn = lambda_.Function(
            self,
            "PreSignUpFn",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=lambda_.Code.from_asset("functions/pre-signup"),
        )

        define_auth_challenge_fn = lambda_.Function(
            self,
            "DefineAuthChallengeFn",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=lambda_.Code.from_asset("functions/define-auth-challenge"),
        )

        create_auth_challenge_fn = lambda_.Function(
            self,
            "CreateAuthChallengeFn",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=lambda_.Code.from_asset("functions/create-auth-challenge"),
            environment={
                "SENDER_EMAIL": "outgoing@dctech.events"
            }
        )

        verify_auth_challenge_fn = lambda_.Function(
            self,
            "VerifyAuthChallengeFn",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=lambda_.Code.from_asset("functions/verify-auth-challenge"),
        )

        # Add SES permissions to create_auth_challenge_fn
        create_auth_challenge_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail", "ses:SendRawEmail"],
                resources=["*"],
            )
        )

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
                pre_sign_up=pre_signup_fn,
                define_auth_challenge=define_auth_challenge_fn,
                create_auth_challenge=create_auth_challenge_fn,
                verify_auth_challenge_response=verify_auth_challenge_fn,
            ),
            auto_verify={"email": True}  # Use this instead of VerificationAttributeType
        )


        # Add Cognito admin permissions to functions that need them
        for fn in [create_auth_challenge_fn, verify_auth_challenge_fn]:
            fn.add_to_role_policy(
                iam.PolicyStatement(
                    actions=[
                        "cognito-idp:AdminGetUser",
                        "cognito-idp:AdminUpdateUserAttributes"
                    ],
                    resources=[self.user_pool.user_pool_arn]
                )
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

        # Create the client
        self.client = self.user_pool.add_client(
            "app-client",
            auth_flows=cognito.AuthFlow(
                custom=True,
                user_password=False,
                user_srp=False,
                admin_user_password=False,
            ),
            prevent_user_existence_errors=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[cognito.OAuthScope.EMAIL],
                callback_urls=["http://localhost:3000"],
                logout_urls=["http://localhost:3000"],
            ),
            generate_secret=False,
        )

        # In the UserPoolStack class, update the permissions for pre_signup_fn:
        define_auth_challenge_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:AdminCreateUser",
                    "cognito-idp:AdminSetUserPassword"
                ],
                resources=[self.user_pool.user_pool_arn]
            )
        )
