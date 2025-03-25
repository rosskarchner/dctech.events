from aws_cdk import (
    Stack,
    Duration,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_certificatemanager as acm,
    aws_apigatewayv2 as apigwv2,  # Changed import
    aws_apigatewayv2_integrations as apigwv2_integrations,  # Added import
    aws_s3 as s3,
    aws_cognito as cognito,
    aws_lambda as lambda_,
    aws_iam as iam,
    RemovalPolicy,
    NestedStack,
    CfnOutput
)
from constructs import Construct

class SignUpStack(NestedStack):
    def __init__(self, scope: Construct, construct_id: str, userpool:cognito.UserPool, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)


        marker_storage = s3.Bucket(
            self,
            "MarkerStorage",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(1),
                    enabled=True
                )
            ]
        )


        signup_function = lambda_.Function(
            self,
            "SignupFunction",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset("functions/signup"),
            memory_size=256,
            timeout=Duration.seconds(30),
            environment={
                "BUCKET": marker_storage.bucket_name,
                "SENDER_EMAIL": "outgoing@dctech.events"
            },
        )

        confirmation_function = lambda_.Function(
            self,
            "ConfirmationFunction",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset("functions/confirm"),
            memory_size=256,
            timeout=Duration.seconds(30),
            environment={
                "BUCKET": marker_storage.bucket_name,
                "USER_POOL_ID": userpool.user_pool_id,
            },
        )
        
        signup_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail", "ses:SendRawEmail"],
                resources=["*"]  # You can restrict this to specific SES ARNs if desired
            )
        )


        confirmation_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "cognito-idp:AdminCreateUser",
                    "cognito-idp:AdminUpdateUserAttributes"
                ],
                resources=[userpool.user_pool_arn]
            )
        )

        marker_storage.grant_read_write(signup_function)
        marker_storage.grant_read_write(confirmation_function)
        

        # Create HTTP API
        self.http_api = apigwv2.HttpApi(
            self,
            "HttpApi",
            api_name="Newsletter API",
            cors_preflight={
                "allow_origins": ['https://dctech.events'],
                "allow_methods": [apigwv2.CorsHttpMethod.POST],
                "allow_headers": ['Content-Type'],
            }
        )
        
        # Add outputs for the API domain
        self.api_endpoint = CfnOutput(
            self,
            "ApiEndpoint",
            value=self.http_api.api_endpoint
        )

        # Create Lambda integration
        signup_integration = apigwv2_integrations.HttpLambdaIntegration(
            "SignupIntegration",
            handler=signup_function
        )

        confirmation_integration = apigwv2_integrations.HttpLambdaIntegration(
            "ConfirmationIntegration",
            handler=confirmation_function
        )
        # Add route
        self.http_api.add_routes(
            path="/signup",
            methods=[apigwv2.HttpMethod.POST],
            integration=signup_integration
        )

        # Add route for confirmation endpoint
        self.http_api.add_routes(
            path="/confirm/{token}",
            methods=[apigwv2.HttpMethod.GET, apigwv2.HttpMethod.POST],
            integration=confirmation_integration
        )
        
