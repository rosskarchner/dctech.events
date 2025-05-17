# Deployment Guide for Cal-Containers

This guide explains how to set up the infrastructure for building and deploying containers to Amazon ECR using GitHub Actions.

## Infrastructure Setup

The project includes a CloudFormation template (`ecr-infrastructure.yaml`) that creates:
- ECR repositories for the frontend and aggregator containers
- IAM role for GitHub Actions with permissions to push to ECR
- OIDC provider configuration for secure authentication between GitHub and AWS

### Deploying the CloudFormation Stack

1. Update the parameters in the template with your GitHub information:
   - `GitHubOrg`: Your GitHub username or organization
   - `GitHubRepo`: The repository name (default: cal-containers)
   - `GitHubBranch`: The branch that triggers deployments (default: main)

2. Deploy the CloudFormation stack:
   ```bash
   aws cloudformation deploy \
     --template-file ecr-infrastructure.yaml \
     --stack-name cal-containers-ecr-infra \
     --capabilities CAPABILITY_NAMED_IAM \
     --parameter-overrides \
       GitHubOrg=your-github-username \
       GitHubRepo=cal-containers \
       GitHubBranch=main
   ```

3. Get the outputs from the CloudFormation stack:
   ```bash
   aws cloudformation describe-stacks \
     --stack-name cal-containers-ecr-infra \
     --query "Stacks[0].Outputs"
   ```

## GitHub Repository Setup

1. Add the following secrets to your GitHub repository:
   - `AWS_ROLE_ARN`: The ARN of the IAM role created by CloudFormation (from the `GitHubActionsRoleARN` output)
   - `ECR_REPOSITORY_FRONTEND`: The name of the frontend ECR repository (`cal-containers-frontend`)
   - `ECR_REPOSITORY_AGGREGATOR`: The name of the aggregator ECR repository (`cal-containers-aggregator`)

2. The GitHub Actions workflow (`.github/workflows/build-and-push.yml`) is already configured to:
   - Trigger on pushes to the main branch
   - Authenticate with AWS using OIDC
   - Build and push the containers to ECR

## Container Deployment

Once the containers are pushed to ECR, you can deploy them using:
- AWS Lambda for the aggregator container
- Amazon ECS, EKS, or App Runner for the frontend container

### Example Lambda Deployment

```bash
aws lambda create-function \
  --function-name cal-aggregator \
  --package-type Image \
  --code ImageUri=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/cal-containers-aggregator:latest \
  --role arn:aws:iam::${AWS_ACCOUNT_ID}:role/lambda-execution-role
```

### Example ECS Deployment

Create an ECS task definition and service that references the frontend container in ECR.

## Maintenance

- The ECR repositories are configured with lifecycle policies to keep only the last 10 images
- Update the GitHub Actions workflow as needed for additional build steps or containers
- Monitor the GitHub Actions runs to ensure successful deployments