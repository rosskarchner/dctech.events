#!/bin/bash
set -e

# Default values
STACK_NAME="dctech-events"
TEMPLATE_FILE="template.yaml"
ENVIRONMENT="dev"
DOMAIN_NAME="dctech.events"
AUTH_DOMAIN_NAME="auth.dctech.events"
REGION=$(aws configure get region || echo "us-east-1")
AGGREGATOR_IMAGE_URI=""
API_IMAGE_URI=""
STATIC_SITE_GENERATOR_IMAGE_URI=""

# Help function
function show_help {
    echo "Usage: $0 [options]"
    echo ""
    echo "Build and deploy the DCTech Events application using SAM"
    echo ""
    echo "Options:"
    echo "  -h, --help                 Show this help message"
    echo "  -s, --stack-name NAME      Set the CloudFormation stack name (default: $STACK_NAME)"
    echo "  -t, --template FILE        Set the CloudFormation template file (default: $TEMPLATE_FILE)"
    echo "  -e, --environment ENV      Set the environment (default: $ENVIRONMENT)"
    echo "  -d, --domain-name DOMAIN   Set the domain name (default: $DOMAIN_NAME)"
    echo "  -a, --auth-domain DOMAIN   Set the auth domain name (default: $AUTH_DOMAIN_NAME)"
    echo "  -r, --region REGION        Set the AWS region (default: $REGION)"
    echo "  -b, --build-only           Build the application without deploying"
    echo "  --delete                   Delete the CloudFormation stack"
    echo "  --aggregator-image URI     Set the Aggregator Lambda container image URI"
    echo "  --api-image URI            Set the API Lambda container image URI"
    echo "  --static-site-image URI    Set the Static Site Generator Lambda container image URI"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -h|--help)
            show_help
            exit 0
            ;;
        -s|--stack-name)
            STACK_NAME="$2"
            shift 2
            ;;
        -t|--template)
            TEMPLATE_FILE="$2"
            shift 2
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -d|--domain-name)
            DOMAIN_NAME="$2"
            shift 2
            ;;
        -a|--auth-domain)
            AUTH_DOMAIN_NAME="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -b|--build-only)
            BUILD_ONLY=true
            shift
            ;;
        --delete)
            DELETE_STACK=true
            shift
            ;;
        --aggregator-image)
            AGGREGATOR_IMAGE_URI="$2"
            shift 2
            ;;
        --api-image)
            API_IMAGE_URI="$2"
            shift 2
            ;;
        --static-site-image)
            STATIC_SITE_GENERATOR_IMAGE_URI="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Check if template file exists
if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "Error: Template file '$TEMPLATE_FILE' not found"
    exit 1
fi

# Function to check if stack exists
function stack_exists {
    aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" &> /dev/null
    return $?
}

# Delete stack if requested
if [ "$DELETE_STACK" = true ]; then
    if stack_exists; then
        echo "Deleting stack '$STACK_NAME'..."
        aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION"
        echo "Waiting for stack deletion to complete..."
        aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$REGION"
        echo "Stack '$STACK_NAME' deleted successfully"
    else
        echo "Stack '$STACK_NAME' does not exist"
    fi
    exit 0
fi

# Build the application if no container images are provided
if [ -z "$AGGREGATOR_IMAGE_URI" ] || [ -z "$API_IMAGE_URI" ] || [ -z "$STATIC_SITE_GENERATOR_IMAGE_URI" ]; then
    echo "Building the application with SAM..."
    sam build --template "$TEMPLATE_FILE" --region "$REGION"
fi

# Exit if build-only flag is set
if [ "$BUILD_ONLY" = true ]; then
    echo "Build completed successfully. Skipping deployment as requested."
    exit 0
fi

# Prepare parameter overrides
PARAMS="DomainName=$DOMAIN_NAME AuthDomainName=$AUTH_DOMAIN_NAME Environment=$ENVIRONMENT"

# Add container image URIs if provided
if [ -n "$AGGREGATOR_IMAGE_URI" ]; then
    PARAMS="$PARAMS AggregatorImageUri=$AGGREGATOR_IMAGE_URI"
fi

if [ -n "$API_IMAGE_URI" ]; then
    PARAMS="$PARAMS ApiImageUri=$API_IMAGE_URI"
fi

if [ -n "$STATIC_SITE_GENERATOR_IMAGE_URI" ]; then
    PARAMS="$PARAMS StaticSiteGeneratorImageUri=$STATIC_SITE_GENERATOR_IMAGE_URI"
fi

# Deploy the application
echo "Deploying the application with SAM..."
sam deploy \
    --stack-name "$STACK_NAME" \
    --capabilities CAPABILITY_IAM \
    --region "$REGION" \
    --parameter-overrides $PARAMS

echo "Deployment completed successfully!"

# Get and display stack outputs
echo "Stack outputs:"
aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query "Stacks[0].Outputs" \
    --output table

echo ""
echo "DCTech Events application deployment complete!"