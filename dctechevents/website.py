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
)
from constructs import Construct


class WebsiteSite(Stack):
    """The Website"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
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
            
            if (host.startsWith('www.')) {
                return {
                    statusCode: 301,
                    statusDescription: 'Moved Permanently',
                    headers: {
                        'location': {
                            value: `https://${host.substring(4)}${request.uri}`
                        }
                    }
                };
            }
            return request;
        }
        """
        redirect_function = cloudfront.Function(
            self,
            "RedirectFunction",
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

        # Create a CloudFront distribution
        distribution = cloudfront.Distribution(
            self,
            "Distribution",
            domain_names=["dctech.events", "www.dctech.events"],
            certificate=cert,
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                function_associations=[
                    cloudfront.FunctionAssociation(
                        function=redirect_function,
                        event_type=cloudfront.FunctionEventType.VIEWER_REQUEST
                    )
                ],
                response_headers_policy=hsts_policy
            ),
            default_root_object="index.html",
        )
        s3deploy.BucketDeployment(
            self,
            "DeployWebsite",
            sources=[s3deploy.Source.asset("./website")],  # Directory containing your website files
            destination_bucket=bucket,
            distribution=distribution,  # This enables CloudFront invalidation
            distribution_paths=["/*"],  # Invalidate all paths
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
