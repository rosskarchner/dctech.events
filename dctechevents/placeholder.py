from aws_cdk import (
    Stack,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_certificatemanager as acm,
    aws_s3 as s3,
    RemovalPolicy,
)
from constructs import Construct


class PlaceholderSite(Stack):
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

        # Create a CloudFront distribution
        distribution = cloudfront.Distribution(
            self,
            "Distribution",
            domain_names=["dctech.events", "www.dctech.events"],
            certificate=cert,
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket)
            ),
            default_root_object="index.html",
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
