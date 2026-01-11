"""
Distribution Stack for DC Tech Events - CloudFront CDN
"""
from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_certificatemanager as acm,
)
from constructs import Construct


class DistributionStack(Stack):
    """Stack for CloudFront distribution"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        project_name: str,
        environment: str,
        api_domain: str,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Parse API Gateway domain from full URL
        # api_domain format: https://xxxxx.execute-api.us-east-1.amazonaws.com/api
        api_domain_name = api_domain.replace("https://", "").replace("http://", "")

        # Extract just the domain part (before the path)
        if "/" in api_domain_name:
            api_domain_name = api_domain_name.split("/")[0]

        # API Gateway origin
        api_origin = origins.HttpOrigin(
            api_domain_name,
            protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
            custom_headers={
                "X-Forwarded-Host": api_domain_name,
            },
        )

        # Cache policy for API responses
        api_cache_policy = cloudfront.CachePolicy(
            self,
            "ApiCachePolicy",
            cache_policy_name=f"{project_name}-API-{environment}",
            comment="Cache policy for API Gateway responses",
            default_ttl=Duration.minutes(5),
            min_ttl=Duration.minutes(1),
            max_ttl=Duration.hours(24),
            cookie_behavior=cloudfront.CacheCookieBehavior.none(),
            header_behavior=cloudfront.CacheHeaderBehavior.allow_list(
                "Accept",
                "Accept-Language",
                "CloudFront-Viewer-Country",
            ),
            query_string_behavior=cloudfront.CacheQueryStringBehavior.all(),
            enable_accept_encoding_gzip=True,
            enable_accept_encoding_brotli=True,
        )

        # Cache policy for static assets (longer TTL)
        static_cache_policy = cloudfront.CachePolicy(
            self,
            "StaticCachePolicy",
            cache_policy_name=f"{project_name}-Static-{environment}",
            comment="Cache policy for static assets",
            default_ttl=Duration.days(7),
            min_ttl=Duration.hours(1),
            max_ttl=Duration.days(365),
            cookie_behavior=cloudfront.CacheCookieBehavior.none(),
            header_behavior=cloudfront.CacheHeaderBehavior.none(),
            query_string_behavior=cloudfront.CacheQueryStringBehavior.none(),
            enable_accept_encoding_gzip=True,
            enable_accept_encoding_brotli=True,
        )

        # Origin request policy to forward query strings
        origin_request_policy = cloudfront.OriginRequestPolicy(
            self,
            "ApiOriginRequestPolicy",
            origin_request_policy_name=f"{project_name}-API-{environment}",
            comment="Forward all query strings and headers to API",
            query_string_behavior=cloudfront.OriginRequestQueryStringBehavior.all(),
            header_behavior=cloudfront.OriginRequestHeaderBehavior.allow_list(
                "Accept",
                "Accept-Language",
                "CloudFront-Viewer-Country",
            ),
        )

        # CloudFront distribution
        self.distribution = cloudfront.Distribution(
            self,
            "Distribution",
            comment=f"{project_name} CDN - {environment}",
            default_behavior=cloudfront.BehaviorOptions(
                origin=api_origin,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=api_cache_policy,
                origin_request_policy=origin_request_policy,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                compress=True,
            ),
            additional_behaviors={
                # Static assets from S3 (if using S3 for assets)
                "/static/*": cloudfront.BehaviorOptions(
                    origin=api_origin,  # Can be changed to S3 origin if needed
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=static_cache_policy,
                    compress=True,
                ),
            },
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,  # US, Canada, Europe
            enable_ipv6=True,
            http_version=cloudfront.HttpVersion.HTTP2_AND_3,
        )

        # Outputs
        CfnOutput(
            self,
            "DistributionDomain",
            value=self.distribution.distribution_domain_name,
            description="CloudFront distribution domain name"
        )

        CfnOutput(
            self,
            "DistributionId",
            value=self.distribution.distribution_id,
            description="CloudFront distribution ID"
        )

        # Store distribution domain for reference
        self.distribution_domain = self.distribution.distribution_domain_name
