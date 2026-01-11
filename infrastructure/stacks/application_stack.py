"""
Application Stack for DC Tech Events - Chalice API
"""
from aws_cdk import (
    Stack,
    CfnOutput,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_s3 as s3,
    aws_s3_deployment as s3_deployment,
    RemovalPolicy,
)
from constructs import Construct
from chalice.cdk import Chalice


class ApplicationStack(Stack):
    """Stack for Chalice API application"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        project_name: str,
        environment: str,
        events_table: dynamodb.Table,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # S3 bucket for static assets and group definitions
        self.assets_bucket = s3.Bucket(
            self,
            "AssetsBucket",
            bucket_name=f"{project_name.lower()}-assets-{environment}",
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            versioned=True,
        )

        # Deploy _groups directory to S3
        s3_deployment.BucketDeployment(
            self,
            "GroupsDeployment",
            sources=[s3_deployment.Source.asset("../_groups")],
            destination_bucket=self.assets_bucket,
            destination_key_prefix="groups/",
        )

        # Deploy static assets
        s3_deployment.BucketDeployment(
            self,
            "StaticAssetsDeployment",
            sources=[s3_deployment.Source.asset("../static")],
            destination_bucket=self.assets_bucket,
            destination_key_prefix="static/",
        )

        # Chalice application
        self.chalice = Chalice(
            self,
            "ChaliceApp",
            source_dir="../chalice-app",
            stage_config={
                "environment_variables": {
                    "DYNAMODB_TABLE_NAME": events_table.table_name,
                    "ASSETS_BUCKET": self.assets_bucket.bucket_name,
                    "ENVIRONMENT": environment,
                },
                "tags": {
                    "Project": project_name,
                    "Environment": environment,
                },
                "manage_iam_role": False,
                "iam_role_arn": self._create_chalice_role(
                    events_table, self.assets_bucket
                ).role_arn,
            },
        )

        # Outputs
        self.api_url = self.chalice.sam_template.get_output("EndpointURL").value

        CfnOutput(
            self,
            "ApiUrl",
            value=self.api_url,
            description="API Gateway endpoint URL"
        )

        CfnOutput(
            self,
            "AssetsBucket",
            value=self.assets_bucket.bucket_name,
            description="S3 bucket for static assets"
        )

    def _create_chalice_role(
        self,
        events_table: dynamodb.Table,
        assets_bucket: s3.Bucket
    ) -> iam.Role:
        """Create IAM role for Chalice Lambda functions"""
        role = iam.Role(
            self,
            "ChaliceRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ],
        )

        # Grant DynamoDB permissions
        events_table.grant_read_data(role)

        # Grant S3 read permissions
        assets_bucket.grant_read(role)

        return role
