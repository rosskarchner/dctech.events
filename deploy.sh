#!/bin/bash
set -e

# Default values
STACK_NAME="dctech-events"
TEMPLATE_FILE="template.yaml"
ENVIRONMENT="dev"
DOMAIN_NAME="dctech.events"
AUTH_DOMAIN_NAME="auth.dctech.events"
REGION=$(aws configure get region || echo "us-east-1")

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

# Build the application
echo "Building the application with SAM..."
sam build --template "$TEMPLATE_FILE" --region "$REGION"

# Exit if build-only flag is set
if [ "$BUILD_ONLY" = true ]; then
    echo "Build completed successfully. Skipping deployment as requested."
    exit 0
fi

# Deploy the application
echo "Deploying the application with SAM..."
sam deploy \
    --stack-name "$STACK_NAME" \
    --capabilities CAPABILITY_IAM \
    --region "$REGION" \
    --parameter-overrides \
        DomainName="$DOMAIN_NAME" \
        AuthDomainName="$AUTH_DOMAIN_NAME" \
        Environment="$ENVIRONMENT"

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