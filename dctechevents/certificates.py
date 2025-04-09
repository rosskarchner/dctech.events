from aws_cdk import (
    Stack,
    aws_route53 as route53,
    aws_certificatemanager as acm,
)
from constructs import Construct

class CertificateStack(Stack):
    """Stack for creating and managing certificates"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Find the hosted zone for dctech.events
        self.hosted_zone = route53.HostedZone.from_lookup(
            self, "HostedZone", domain_name="dctech.events"
        )
        
        # Create a wildcard certificate for all subdomains
        self.certificate = acm.Certificate(
            self, "WildcardCertificate",
            domain_name="dctech.events",
            subject_alternative_names=["*.dctech.events"],
            validation=acm.CertificateValidation.from_dns(self.hosted_zone)
        )
