#!/bin/bash
set -e

# Default values
STACK_NAME="cal-containers-ecr-infra"
TEMPLATE_FILE="ecr-infrastructure.yaml"
GITHUB_ORG="rosskarchner"
GITHUB_REPO="cal-containers"
GITHUB_BRANCH="main"
IMAGE_RETENTION=10

# Help function
function show_help {
    echo "Usage: $0 [options]"
    echo ""
    echo "Deploy or update the ECR infrastructure CloudFormation stack"
    echo ""
    echo "Options:"
    echo "  -h, --help                 Show this help message"
    echo "  -s, --stack-name NAME      Set the CloudFormation stack name (default: $STACK_NAME)"
    echo "  -t, --template FILE        Set the CloudFormation template file (default: $TEMPLATE_FILE)"
    echo "  -o, --github-org ORG       Set the GitHub organization/username (default: $GITHUB_ORG)"
    echo "  -r, --github-repo REPO     Set the GitHub repository name (default: $GITHUB_REPO)"
    echo "  -b, --github-branch BRANCH Set the GitHub branch name (default: $GITHUB_BRANCH)"
    echo "  -i, --image-retention NUM  Set the number of images to retain (default: $IMAGE_RETENTION)"
    echo "  -v, --validate             Validate the CloudFormation template without deploying"
    echo "  -d, --delete               Delete the CloudFormation stack"
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
        -o|--github-org)
            GITHUB_ORG="$2"
            shift 2
            ;;
        -r|--github-repo)
            GITHUB_REPO="$2"
            shift 2
            ;;
        -b|--github-branch)
            GITHUB_BRANCH="$2"
            shift 2
            ;;
        -i|--image-retention)
            IMAGE_RETENTION="$2"
            shift 2
            ;;
        -v|--validate)
            VALIDATE_ONLY=true
            shift
            ;;
        -d|--delete)
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

# Validate image retention value
if ! [[ "$IMAGE_RETENTION" =~ ^[0-9]+$ ]] || [ "$IMAGE_RETENTION" -lt 1 ] || [ "$IMAGE_RETENTION" -gt 100 ]; then
    echo "Error: Image retention must be a number between 1 and 100"
    exit 1
fi

# Function to check if stack exists
function stack_exists {
    aws cloudformation describe-stacks --stack-name "$STACK_NAME" &> /dev/null
    return $?
}

# Delete stack if requested
if [ "$DELETE_STACK" = true ]; then
    if stack_exists; then
        echo "Deleting stack '$STACK_NAME'..."
        aws cloudformation delete-stack --stack-name "$STACK_NAME"
        echo "Waiting for stack deletion to complete..."
        aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME"
        echo "Stack '$STACK_NAME' deleted successfully"
    else
        echo "Stack '$STACK_NAME' does not exist"
    fi
    exit 0
fi

# Validate template
echo "Validating CloudFormation template '$TEMPLATE_FILE'..."
aws cloudformation validate-template --template-body "file://$TEMPLATE_FILE"

if [ "$VALIDATE_ONLY" = true ]; then
    echo "Template validation successful"
    exit 0
fi

# Deploy or update stack
PARAMS=(
    "ParameterKey=GitHubOrg,ParameterValue=$GITHUB_ORG"
    "ParameterKey=GitHubRepo,ParameterValue=$GITHUB_REPO"
    "ParameterKey=GitHubBranch,ParameterValue=$GITHUB_BRANCH"
    "ParameterKey=StackEnvironment,ParameterValue=dev"
    "ParameterKey=ImageRetentionCount,ParameterValue=$IMAGE_RETENTION"
)

# Convert params array to string
PARAMS_STR=$(IFS=$' '; echo "${PARAMS[*]}")

# Check if stack exists
if stack_exists; then
    echo "Updating stack '$STACK_NAME'..."
    OPERATION="update"
else
    echo "Creating stack '$STACK_NAME'..."
    OPERATION="create"
fi

# Deploy the stack
aws cloudformation deploy \
    --template-file "$TEMPLATE_FILE" \
    --stack-name "$STACK_NAME" \
    --parameter-overrides ${PARAMS_STR} \
    --capabilities CAPABILITY_NAMED_IAM \
    --tags Environment="dev" Application="cal-containers"

echo "Stack $OPERATION completed successfully"

# Get and display stack outputs
echo "Stack outputs:"
aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs" \
    --output table

echo ""
echo "ECR infrastructure deployment complete!"
echo "You can use these values in your GitHub Actions workflow."