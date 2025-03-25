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
)
from constructs import Construct
from .signup import SignUpStack


class WebsiteSite(Stack):
    """The Website"""

    def __init__(self, scope: Construct, construct_id: str, *, api_stack=None,userpoolstack=None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Get the region from the environment
        region = Stack.of(self).region
        
        # Store the API stack reference
        self.api_stack = api_stack
        
        hosted_zone = route53.HostedZone.from_lookup(
            self, "Zone", domain_name="dctech.events"
        )
        # Create an S3 bucket to store the website content
        bucket = s3.Bucket(
            self,
            "WebsiteBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )
        

        user_pool = userpoolstack.user_pool
        
        # Create the SignUp API as a nested stack
        signup_stack = SignUpStack(
            self, 
            "SignUpStack",
            userpool=user_pool
        )
        
        # Get the API Gateway from the nested stack
        # http_api = signup_stack.http_api

        cert = acm.Certificate(
            self,
            "Certificate",
            domain_name="dctech.events",
            subject_alternative_names=["*.dctech.events"],
            validation=acm.CertificateValidation.from_dns(hosted_zone),
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
                
                // Handle directory indexes
                if (uri.endsWith('/')) {
                    request.uri += 'index.html';
                    return request;
                }
                
                // If uri doesn't have an extension, redirect to add trailing slash
                if (!uri.includes('.')) {
                    return {
                        statusCode: 301,
                        statusDescription: 'Moved Permanently',
                        headers: {
                            'location': { value: uri + '/' }
                        }
                    };
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
        
        # Create a CloudFront distribution with updated behaviors
        distribution = cloudfront.Distribution(
            self,
            "Distribution",
            domain_names=["dctech.events", "www.dctech.events"],
            certificate=cert,
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            default_behavior=cloudfront.BehaviorOptions(
                # Default behavior routes to S3 bucket instead of API
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
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
            additional_behaviors={
                # Route /confirm/* path to the API Gateway
                "/confirm/*": cloudfront.BehaviorOptions(
                    origin=origins.HttpOrigin(
                        domain_name=f"{signup_stack.http_api.api_id}.execute-api.{self.region}.amazonaws.com",
                        protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                ),

                # Route /signup path to the API Gateway
                "/signup": cloudfront.BehaviorOptions(
                    origin=origins.HttpOrigin(
                        domain_name=f"{signup_stack.http_api.api_id}.execute-api.{self.region}.amazonaws.com",
                        protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                ),

                
                "/api/*": cloudfront.BehaviorOptions(
                    origin=origins.HttpOrigin(
                        domain_name=f"{self.api_stack.http_api.api_id}.execute-api.us-east-1.amazonaws.com",
                        protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
                        origin_path=""
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                ),
            },
            default_root_object="index.html",
        )
        s3deploy.BucketDeployment(
            self,
            "DeployWebsite",
            sources=[s3deploy.Source.asset("./website")],  # Directory containing your website files
            destination_bucket=bucket,
            distribution=distribution,  # This enables CloudFront invalidation
            distribution_paths=["/*"],  # Invalidate all paths
            destination_key_prefix=""  # Put all website files under /static/
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
        
        # Output the distribution domain name for reference
        CfnOutput(
            self,
            "DistributionDomainName",
            value=distribution.distribution_domain_name,
            description="The domain name of the CloudFront distribution"
        )
