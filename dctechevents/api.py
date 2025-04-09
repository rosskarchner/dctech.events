from aws_cdk import (
    Stack,
    Duration,
    aws_dynamodb as dynamodb,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as integrations,
    aws_apigatewayv2_authorizers as authorizers,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_s3 as s3,
    aws_cognito as cognito,
    aws_certificatemanager as acm,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_events as events,
    aws_events_targets as events_targets,
    CustomResource,
    custom_resources as cr,
    RemovalPolicy
)
from datetime import datetime
from constructs import Construct


class ApiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, rendered_site_bucket:s3.Bucket, user_pool: cognito.UserPool, user_pool_client:cognito.UserPoolClient, user_pool_stack:Stack, admin_group: cognito.CfnUserPoolGroup, editor_group: cognito.CfnUserPoolGroup, certificate=None, hosted_zone=None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Define the scopes based on your Cognito groups
        admin_group_scope = "aws.cognito.signin.user.admin"
        editor_group_scope = "aws.cognito.signin.user.editor"
        
        # Use the provided hosted zone
        self.hosted_zone = hosted_zone
        
        # Use the provided certificate
        api_certificate = certificate
        
        # Create API Gateway with custom domain, JWT authorizer, and CORS configuration
        domain_name = apigwv2.DomainName(
            self, "ApiDomainName",
            domain_name="api.dctech.events",
            certificate=api_certificate
        )
        
        self.http_api = apigwv2.HttpApi(
            self, "HttpApi",
            api_name="Events API",
            create_default_stage=True,
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_methods=[
                    apigwv2.CorsHttpMethod.GET,
                    apigwv2.CorsHttpMethod.POST,
                    apigwv2.CorsHttpMethod.PUT,
                    apigwv2.CorsHttpMethod.DELETE,
                    apigwv2.CorsHttpMethod.PATCH,
                    apigwv2.CorsHttpMethod.OPTIONS
                ],
                allow_origins=[
                    "https://dctech.events",
                    "https://www.dctech.events",
                    "http://localhost:3000"  # For local development
                ],
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Amz-Date",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                    "hx-request",
                    "hx-current-url",
                    "hx-target",
                    "hx-trigger",
                    "hx-boost"
                ],
                allow_credentials=True,
                max_age=Duration.hours(1)
            ),
            default_domain_mapping=apigwv2.DomainMappingOptions(
                domain_name=domain_name
            )
        )
        
        # Create DNS records for the API Gateway
        api_target = route53.RecordTarget.from_alias(
            targets.ApiGatewayv2DomainProperties(
                regional_domain_name=domain_name.regional_domain_name,
                regional_hosted_zone_id=domain_name.regional_hosted_zone_id
            )
        )
        
        # Create A record for IPv4
        route53.ARecord(
            self, "ApiARecord",
            zone=self.hosted_zone,
            record_name="api",
            target=api_target
        )
        
        # Create AAAA record for IPv6
        route53.AaaaRecord(
            self, "ApiAAAARecord",
            zone=self.hosted_zone,
            record_name="api",
            target=api_target
        )
        
        self.events_table = dynamodb.Table(
            self, "EventsTable",
            partition_key=dynamodb.Attribute(
                name="week",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="sort",
                type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY,
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        self.groups_table = dynamodb.Table(
            self, "GroupsTable",
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY,
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )
        
        # Add GSI for approval status
        self.groups_table.add_global_secondary_index(
            index_name="approval-status-index",
            partition_key=dynamodb.Attribute(
                name="approval_status",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="organization_name",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        # Add GSI for source-based queries
        self.events_table.add_global_secondary_index(
            index_name="group-index",
            partition_key=dynamodb.Attribute(
                name="sourceId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING
            )
        )

        # Add GSI for status-based queries
        self.events_table.add_global_secondary_index(
            index_name="status-index",
            partition_key=dynamodb.Attribute(
                name="status",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="date",
                type=dynamodb.AttributeType.STRING
            )
        )



        authenticated_functions = {
            "submit": lambda_.Function(
                self, "SubmitEventFunction",
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="index.handler",
                code=lambda_.Code.from_asset("functions/submit_event"),
                environment={
                    "TABLE_NAME": self.events_table.table_name,
                    "USER_POOL_ID": user_pool.user_pool_id
                },
                initial_policy=[
                    iam.PolicyStatement(
                        actions=[
                            "cognito-idp:ListUsers"
                        ],
                        resources=[user_pool.user_pool_arn]
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "dynamodb:PutItem"
                        ],
                        resources=[self.events_table.table_arn]
                    )
                ]
            ),

            "suggest_group_form": lambda_.Function(
                self, "SuggestGroupFormFunction",
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="index.handler",
                code=lambda_.Code.from_asset("functions/suggest_group_form"),
                environment={
                    "USER_POOL_ID": user_pool.user_pool_id
                }
            ),
            "suggest_group": lambda_.Function(
                self, "SuggestGroupFunction",
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="index.handler",
                code=lambda_.Code.from_asset("functions/suggest_group"),
                environment={
                    "GROUPS_TABLE": self.groups_table.table_name,
                    "USER_POOL_ID": user_pool.user_pool_id
                },
                initial_policy=[
                    iam.PolicyStatement(
                        actions=[
                            "dynamodb:PutItem"
                        ],
                        resources=[self.groups_table.table_arn]
                    )
                ]
            ),

        }

        editor_functions = {
            "approve": lambda_.Function(
                self, "ApproveEventFunction",
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="index.handler",
                code=lambda_.Code.from_asset("functions/approve_event"),
                environment={
                    "TABLE_NAME": self.events_table.table_name
                }
            ),
            "update": lambda_.Function(
                self, "UpdateEventFunction",
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="index.handler",
                code=lambda_.Code.from_asset("functions/update_event"),
                environment={
                    "TABLE_NAME": self.events_table.table_name
                }
            ),
            "delete": lambda_.Function(
                self, "DeleteEventFunction",
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="index.handler",
                code=lambda_.Code.from_asset("functions/delete_event"),
                environment={
                    "TABLE_NAME": self.events_table.table_name
                }
            )
        }


        
        for func in authenticated_functions.values():
            self.events_table.grant_write_data(func)
        
        for func in editor_functions.values():
            self.events_table.grant_full_access(func)

        
        # Store the API endpoint for reference in other stacks
        self.api_endpoint = self.http_api.api_endpoint
        
        # Create Cognito authorizer
        authorizer = authorizers.HttpJwtAuthorizer(
            "ApiAuthorizer",
            jwt_issuer=f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool.user_pool_id}",
            jwt_audience=[user_pool_client.user_pool_client_id],
            identity_source=["$request.header.Authorization"],
        )

        # Authenticated endpoints
        self.http_api.add_routes(
            path="/api/events",
            methods=[apigwv2.HttpMethod.POST],
            integration=integrations.HttpLambdaIntegration(
                "SubmitEventIntegration",
                handler=authenticated_functions["submit"]
            ),
            authorizer=authorizer
        )
        
        # Group suggestion form endpoint
        self.http_api.add_routes(
            path="/api/groups/suggest-form",
            methods=[apigwv2.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration(
                "SuggestGroupFormIntegration",
                handler=authenticated_functions["suggest_group_form"]
            ),
            authorizer=authorizer
        )
        
        # Group submission endpoint
        self.http_api.add_routes(
            path="/api/groups",
            methods=[apigwv2.HttpMethod.POST],
            integration=integrations.HttpLambdaIntegration(
                "SuggestGroupIntegration",
                handler=authenticated_functions["suggest_group"]
            ),
            authorizer=authorizer
        )
        
        # Login redirect endpoint - public, redirects to Cognito hosted UI
        login_redirect_function = lambda_.Function(
            self, "LoginRedirectFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_asset("functions/login_redirect"),
            environment={
                "USER_POOL_ID": user_pool.user_pool_id,
                "CLIENT_ID": user_pool_client.user_pool_client_id,
                "DOMAIN": "auth.dctech.events"
            }
        )
        
        self.http_api.add_routes(
            path="/api/login-redirect",
            methods=[apigwv2.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration(
                "LoginRedirectIntegration",
                handler=login_redirect_function
            )
        )

        # Editor/Admin endpoints
        self.http_api.add_routes(
            path="/api/events/{id}/approve",
            methods=[apigwv2.HttpMethod.POST],
            integration=integrations.HttpLambdaIntegration(
                "ApproveEventIntegration",
                handler=editor_functions["approve"]
            ),
            authorizer=authorizer
        )

        self.http_api.add_routes(
            path="/api/events/{id}",
            methods=[apigwv2.HttpMethod.PUT],
            integration=integrations.HttpLambdaIntegration(
                "UpdateEventIntegration",
                handler=editor_functions["update"]
            ),
            authorizer=authorizer
        )

        self.http_api.add_routes(
            path="/api/events/{id}",
            methods=[apigwv2.HttpMethod.DELETE],
            integration=integrations.HttpLambdaIntegration(
                "DeleteEventIntegration",
                handler=editor_functions["delete"]
            ),
            authorizer=authorizer
        )

        # Create a Lambda function to render pages to the render bucket
        render_function = lambda_.Function(
            self,
            "RenderFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_asset("functions/renderpage", 
                bundling={
                    "image": lambda_.Runtime.PYTHON_3_12.bundling_image,
                    "command": [
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output"
                    ]
                }
            ),
            environment={
                "RENDER_BUCKET": rendered_site_bucket.bucket_name
            },
            timeout=Duration.seconds(30)
        )
        
        # Grant the Lambda function permission to write to the render bucket
        rendered_site_bucket.grant_read_write(render_function)
        
        # Create an EventBridge rule to trigger the render function periodically
        render_rule = events.Rule(
            self,
            "RenderSchedule",
            schedule=events.Schedule.rate(Duration.minutes(30))  # Run every 30 minutes
        )
        
        # Add the Lambda function as a target for the EventBridge rule
        render_rule.add_target(events_targets.LambdaFunction(render_function))
        
        # Create auth callback fragment endpoint
        auth_callback_fragment_function = lambda_.Function(
            self, "AuthCallbackFragmentFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_asset("functions/auth_callback_fragment"),
            environment={
                "USER_POOL_ID": user_pool.user_pool_id,
                "CLIENT_ID": user_pool_client.user_pool_client_id,
                "REGION": self.region
            }
        )
        
        # Add route for auth callback fragment
        self.http_api.add_routes(
            path="/api/auth-callback-fragment",
            methods=[apigwv2.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration(
                "AuthCallbackFragmentIntegration",
                handler=auth_callback_fragment_function
            )
        )
        
