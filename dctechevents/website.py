import os
from aws_cdk import (
    Stack,
    Duration,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_certificatemanager as acm,
    aws_s3 as s3,
    RemovalPolicy,
    aws_s3_deployment as s3deploy,
    aws_apigatewayv2 as apigwv2,
    aws_cognito as cognito,
    CfnOutput,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_events as aws_events,
    aws_events_targets as aws_events_targets,
    CustomResource,
    custom_resources as cr,
)
from datetime import datetime
from constructs import Construct


class WebsiteStack(Stack):
    """The Website"""

    def __init__(self, scope: Construct, construct_id: str, *, certificate=None, hosted_zone=None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Get the region from the environment
        region = Stack.of(self).region
        
        # Use the provided hosted zone
        self.hosted_zone = hosted_zone
        
        # Create an S3 bucket to store the website content
        self.rendered_site_bucket = s3.Bucket(
            self,
            "RenderedBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )


        function_code = """
            function handler(event) {
                var request = event.request;
                var headers = request.headers;
                var host = headers.host.value;
                var uri = request.uri;
                
                // Handle www redirect first
                if (host.startsWith('www.')) {
                    return {
                        statusCode: 301,
                        statusDescription: 'Moved Permanently',
                        headers: {
                            'location': {
                                value: `https://${host.substring(4)}${uri}`
                            }
                        }
                    };
                }
                
                // Handle root path specifically
                if (uri === '/') {
                    // Keep the URI as is for root
                    return request;
                }
                
                // Handle paths without trailing slash - redirect to add trailing slash
                // Only redirect if the URI doesn't have an extension (like .html, .css, .js, etc.)
                if (!uri.endsWith('/') && uri.indexOf('.') === -1) {
                    return {
                        statusCode: 301,
                        statusDescription: 'Moved Permanently',
                        headers: {
                            'location': {
                                value: `https://${host}${uri}/`
                            }
                        }
                    };
                }
                
                // Handle directory paths with trailing slash - serve index.html
                if (uri.endsWith('/') && uri !== '/') {
                    // Modify the URI to point to the index.html file in that directory
                    request.uri = uri + 'index.html';
                }
                
                return request;
            }
            """
        combined_function = cloudfront.Function(
            self,
            "CombinedViewerRequestFunction",
            code=cloudfront.FunctionCode.from_inline(function_code),
            runtime=cloudfront.FunctionRuntime.JS_2_0
        )


        # Create response headers policy for HSTS
        hsts_policy = cloudfront.ResponseHeadersPolicy(
            self,
            "HSTSPolicy",
            response_headers_policy_name="HSTSPolicy",
            security_headers_behavior=cloudfront.ResponseSecurityHeadersBehavior(
                strict_transport_security=cloudfront.ResponseHeadersStrictTransportSecurity(
                    access_control_max_age= Duration.days(365 * 2),
                    include_subdomains=True,
                    preload=True,
                    override=True
                )
            )
        )
        
        
        # Grant CloudFront access to the render bucket
        self.rendered_site_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=[self.rendered_site_bucket.arn_for_objects("*")],
                principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
                conditions={
                    "StringEquals": {
                        "AWS:SourceArn": f"arn:aws:cloudfront::{self.account}:distribution/*"
                    }
                }
            )
        )
        
        # Create a CloudFront distribution with updated behaviors
        distribution = cloudfront.Distribution(
            self,
            "Distribution",
            domain_names=["dctech.events", "www.dctech.events"],
            certificate=certificate,
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            default_behavior=cloudfront.BehaviorOptions(
                # Set rendered_site_bucket as the default origin
                origin=origins.S3BucketOrigin.with_origin_access_control(self.rendered_site_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                function_associations=[
                    cloudfront.FunctionAssociation(
                        function=combined_function,
                        event_type=cloudfront.FunctionEventType.VIEWER_REQUEST
                    ),
                ],
                response_headers_policy=hsts_policy
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=404,
                    response_page_path="/404.html",
                    ttl=Duration.minutes(30)
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_page_path="/404.html",
                    ttl=Duration.minutes(30)
                )
            ]
        )

        ipv4 = route53.ARecord(
            self,
            "ipv4Arecord",
            zone=hosted_zone,
            record_name="dctech.events",
            target=route53.RecordTarget.from_alias(
                targets.CloudFrontTarget(distribution)
            ),
        )

        ipv6 = route53.AaaaRecord(
            self,
            "ipv6Arecord",
            zone=hosted_zone,
            record_name="dctech.events",
            target=route53.RecordTarget.from_alias(
                targets.CloudFrontTarget(distribution)
            ),
        )
        wwwipv4 = route53.ARecord(
            self,
            "wwwipv4Arecord",
            zone=hosted_zone,
            record_name="www.dctech.events",
            target=route53.RecordTarget.from_alias(
                targets.CloudFrontTarget(distribution)
            ),
        )

        wwwipv6 = route53.AaaaRecord(
            self,
            "wwwipv6Arecord",
            zone=hosted_zone,
            record_name="www.dctech.events",
            target=route53.RecordTarget.from_alias(
                targets.CloudFrontTarget(distribution)
            ),
        )
        
        # Deploy static files from ./website/static to the /static directory in the rendered_site_bucket
        s3deploy.BucketDeployment(
            self,
            "DeployStaticFiles",
            sources=[s3deploy.Source.asset("website/")],
            destination_bucket=self.rendered_site_bucket,
            prune=False,  # Don't remove files that aren't in the source
            retain_on_delete=False,  # Clean up files when the stack is deleted
        )
