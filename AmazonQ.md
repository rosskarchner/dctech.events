# Using CloudFront with API Gateway without Lambda@Edge

This document explains how to set up CloudFront to work with API Gateway without requiring Lambda@Edge functions.

## Solution Overview

The solution uses CloudFront's built-in capabilities to route traffic to different origins based on path patterns. For API Gateway endpoints, we use HTTP origins that point directly to the API Gateway domain.

### Key Components:

1. **CloudFront Distribution**: Routes traffic based on path patterns
2. **S3 Bucket**: Serves static content
3. **API Gateway**: Handles dynamic requests
4. **Path-Based Routing**: Different paths route to different origins

## Implementation Details

The implementation uses the AWS CDK to define the infrastructure. Here's how it works:

1. **Static Content**: Served from an S3 bucket
2. **API Endpoints**: Routed directly to API Gateway
3. **Path Patterns**: Define which requests go to which origin

### Code Example

```python
# Route /signup path to the API Gateway
"/signup": cloudfront.BehaviorOptions(
    origin=origins.HttpOrigin(
        domain_name=f"{signup_stack.http_api.api_id}.execute-api.{self.region}.amazonaws.com",
        protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY
    ),
    # Other behavior options...
)
```

## Benefits

1. **Simplified Architecture**: No Lambda@Edge functions to manage
2. **Reduced Latency**: Direct routing without additional processing
3. **Lower Cost**: No Lambda@Edge execution costs
4. **Easier Maintenance**: Fewer components to troubleshoot

## Limitations

1. **Limited Request Manipulation**: Without Lambda@Edge, you can't modify requests or responses
2. **Static Routing**: Routes are defined at deployment time
3. **No Dynamic Origin Selection**: Origins must be known at deployment time

## Conclusion

This approach provides a simpler way to integrate CloudFront with API Gateway without the complexity of Lambda@Edge. It's suitable for most use cases where you don't need to modify requests or responses dynamically.
