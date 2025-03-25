from aws_cdk import (
    Stack,
    Duration,
    aws_dynamodb as dynamodb,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as integrations,
    aws_apigatewayv2_authorizers as authorizers,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_cognito as cognito,
    aws_certificatemanager as acm,
    aws_route53 as route53,
    aws_route53_targets as targets,
    RemovalPolicy
)
from constructs import Construct


class ApiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, user_pool: cognito.UserPool,user_pool_client:cognito.UserPoolClient, admin_group: cognito.CfnUserPoolGroup, editor_group: cognito.CfnUserPoolGroup, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Define the scopes based on your Cognito groups
        admin_group_scope = "aws.cognito.signin.user.admin"
        editor_group_scope = "aws.cognito.signin.user.editor"
        # Find the hosted zone for dctech.events

        # Create DynamoDB tables
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


        self.sources_table = dynamodb.Table(
            self, "SourcesTable",
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY,
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        # Add GSI for source-based queries
        self.events_table.add_global_secondary_index(
            index_name="source-index",
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

        # Create Lambda functions for events
        public_functions = {
            "list_events": lambda_.Function(
                self, "ListEventsFunction",
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="index.handler",
                code=lambda_.Code.from_asset("functions/list_events"),
                environment={
                    "TABLE_NAME": self.events_table.table_name
                }
            ),
            "get_event": lambda_.Function(
                self, "GetEventFunction",
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="index.handler",
                code=lambda_.Code.from_asset("functions/get_event"),
                environment={
                    "TABLE_NAME": self.events_table.table_name
                }
            ),
            "list_sources": lambda_.Function(
                self, "ListSourcesFunction",
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="index.handler",
                code=lambda_.Code.from_asset("functions/list_sources"),
                environment={
                    "TABLE_NAME": self.sources_table.table_name
                }
            ),
            "get_source": lambda_.Function(
                self, "GetSourceFunction",
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="get_source.handler",
                code=lambda_.Code.from_asset("functions/get_source"),
                environment={
                    "TABLE_NAME": self.sources_table.table_name
                }
            )
        }

        authenticated_functions = {
            "check_permissions": lambda_.Function(
                self, "CheckPermissionsFunction",
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="index.handler",
                code=lambda_.Code.from_asset("functions/check_permissions"),
                environment={
                    "ADMIN_GROUP_NAME": admin_group.group_name,
                    "EDITOR_GROUP_NAME": editor_group.group_name
                }
            ),
            "submit": lambda_.Function(
                self, "SubmitEventFunction",
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="index.handler",
                code=lambda_.Code.from_asset("functions/submit_event"),
                environment={
                    "TABLE_NAME": self.events_table.table_name
                }
            ),
            "update_own": lambda_.Function(
                self, "UpdateOwnEventFunction",
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="index.handler",
                code=lambda_.Code.from_asset("functions/update_own_event"),
                environment={
                    "TABLE_NAME": self.events_table.table_name
                }
            )
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

        admin_functions = {
            "create_source": lambda_.Function(
                self, "CreateSourceFunction",
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="index.handler",
                code=lambda_.Code.from_asset("functions/create_source"),
                environment={
                    "TABLE_NAME": self.sources_table.table_name
                }
            ),
            "update_source": lambda_.Function(
                self, "UpdateSourceFunction",
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="index.handler",
                code=lambda_.Code.from_asset("functions/update_source"),
                environment={
                    "TABLE_NAME": self.sources_table.table_name
                }
            ),
            "delete_source": lambda_.Function(
                self, "DeleteSourceFunction",
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="index.handler",
                code=lambda_.Code.from_asset("functions/delete_source"),
                environment={
                    "TABLE_NAME": self.sources_table.table_name
                }
            )
        }

        # Grant permissions
        for func in public_functions.values():
            if 'source' in func.function_name.lower():
                self.sources_table.grant_read_data(func)
            else:
                self.events_table.grant_read_data(func)
        
        for func in authenticated_functions.values():
            self.events_table.grant_write_data(func)
        
        for func in editor_functions.values():
            self.events_table.grant_full_access(func)

        for func in admin_functions.values():
            self.sources_table.grant_full_access(func)

        # Create API Gateway
        self.http_api = apigwv2.HttpApi(
            self, "HttpApi",
            api_name="Events API",
            cors_preflight={
                "allow_origins": [
                    "https://dctech.events",
                    "https://www.dctech.events"
                ],
                "allow_methods": [
                    apigwv2.CorsHttpMethod.GET,
                    apigwv2.CorsHttpMethod.POST,
                    apigwv2.CorsHttpMethod.PUT,
                    apigwv2.CorsHttpMethod.DELETE,
                    apigwv2.CorsHttpMethod.PATCH,
                    apigwv2.CorsHttpMethod.OPTIONS,
                ],
                "allow_headers": [
                    "Content-Type",
                    "Authorization",
                    "X-Api-Key",
                ],
                "allow_credentials": True,
                "max_age": Duration.days(1)
            },
            create_default_stage=True,
        )
        
        
        # Create the login form Lambda function
        login_form_function = lambda_.Function(
            self, "LoginFormFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_asset("functions/login_form"),
            environment={
                "CLIENT_ID": user_pool_client.user_pool_client_id
            }
        )
        

        
        # Add login form endpoint
        self.http_api.add_routes(
            path="/login",
            methods=[apigwv2.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration(
                "LoginFormIntegration",
                handler=login_form_function
            )
        )
        
        # Store the API endpoint for reference in other stacks
        self.api_endpoint = self.http_api.api_endpoint

        
       # Create Cognito authorizer
        authorizer = authorizers.HttpJwtAuthorizer(
            "ApiAuthorizer",
            jwt_issuer=f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool.user_pool_id}",
            jwt_audience=[user_pool_client.user_pool_client_id],
            identity_source=["$request.header.Authorization"],
        )

        # Add routes with integrations
        # Public endpoints
        self.http_api.add_routes(
            path="/api/events",
            methods=[apigwv2.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration(
                "ListEventsIntegration",
                handler=public_functions["list_events"]
            )
        )

        self.http_api.add_routes(
            path="/api/events/{id}",
            methods=[apigwv2.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration(
                "GetEventIntegration",
                handler=public_functions["get_event"]
            )
        )

        self.http_api.add_routes(
            path="/api/sources",
            methods=[apigwv2.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration(
                "ListSourcesIntegration",
                handler=public_functions["list_sources"]
            )
        )

        self.http_api.add_routes(
            path="/api/sources/{id}",
            methods=[apigwv2.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration(
                "GetSourceIntegration",
                handler=public_functions["get_source"]
            )
        )

        # Authenticated endpoints
        self.http_api.add_routes(
            path="/api/check-permissions",
            methods=[apigwv2.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration(
                "CheckPermissionsIntegration",
                handler=authenticated_functions["check_permissions"]
            ),
            authorizer=authorizer
        )

        self.http_api.add_routes(
            path="/api/events",
            methods=[apigwv2.HttpMethod.POST],
            integration=integrations.HttpLambdaIntegration(
                "SubmitEventIntegration",
                handler=authenticated_functions["submit"]
            ),
            authorizer=authorizer
        )

        self.http_api.add_routes(
            path="/api/events/{id}",
            methods=[apigwv2.HttpMethod.PATCH],
            integration=integrations.HttpLambdaIntegration(
                "UpdateOwnEventIntegration",
                handler=authenticated_functions["update_own"]
            ),
            authorizer=authorizer
        )

        # Editor/Admin endpoints
        self.http_api.add_routes(
            path="/api/events/{id}/approve",
            methods=[apigwv2.HttpMethod.POST],
            integration=integrations.HttpLambdaIntegration(
                "ApproveEventIntegration",
                handler=editor_functions["approve"]
            ),
            authorizer=authorizer,
            authorization_scopes=[editor_group_scope, admin_group_scope]
        )

        self.http_api.add_routes(
            path="/api/events/{id}",
            methods=[apigwv2.HttpMethod.PUT],
            integration=integrations.HttpLambdaIntegration(
                "UpdateEventIntegration",
                handler=editor_functions["update"]
            ),
            authorizer=authorizer,
            authorization_scopes=[editor_group_scope, admin_group_scope]
        )

        self.http_api.add_routes(
            path="/api/events/{id}",
            methods=[apigwv2.HttpMethod.DELETE],
            integration=integrations.HttpLambdaIntegration(
                "DeleteEventIntegration",
                handler=editor_functions["delete"]
            ),
            authorizer=authorizer,
            authorization_scopes=[editor_group_scope, admin_group_scope]
        )

        # Admin only endpoints
        self.http_api.add_routes(
            path="/api/sources",
            methods=[apigwv2.HttpMethod.POST],
            integration=integrations.HttpLambdaIntegration(
                "CreateSourceIntegration",
                handler=admin_functions["create_source"]
            ),
            authorizer=authorizer,
            authorization_scopes=[admin_group_scope]
        )

        self.http_api.add_routes(
            path="/api/sources/{id}",
            methods=[apigwv2.HttpMethod.PUT],
            integration=integrations.HttpLambdaIntegration(
                "UpdateSourceIntegration",
                handler=admin_functions["update_source"]
            ),
            authorizer=authorizer,
            authorization_scopes=[admin_group_scope]
        )

        self.http_api.add_routes(
            path="/api/sources/{id}",
            methods=[apigwv2.HttpMethod.DELETE],
            integration=integrations.HttpLambdaIntegration(
                "DeleteSourceIntegration",
                handler=admin_functions["delete_source"]
            ),
            authorizer=authorizer,
            authorization_scopes=[admin_group_scope]
        )
