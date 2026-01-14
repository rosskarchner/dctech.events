#!/bin/bash
# Deployment Readiness Check Script
# Validates prerequisites and configuration before AWS deployment

set -e

COLOR_RED='\033[0;31m'
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[1;33m'
COLOR_RESET='\033[0m'

CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNING=0

print_check() {
  local message=$1
  local status=$2
  
  case $status in
    pass)
      echo -e "${COLOR_GREEN}✓${COLOR_RESET} $message"
      ((CHECKS_PASSED++))
      ;;
    fail)
      echo -e "${COLOR_RED}✗${COLOR_RESET} $message"
      ((CHECKS_FAILED++))
      ;;
    warn)
      echo -e "${COLOR_YELLOW}⚠${COLOR_RESET} $message"
      ((CHECKS_WARNING++))
      ;;
  esac
}

echo "🔍 DC Tech Events - Deployment Readiness Check"
echo "================================================"
echo ""

# Check 1: AWS CLI
echo "📋 Checking AWS CLI..."
if command -v aws &> /dev/null; then
  aws_version=$(aws --version | cut -d' ' -f1)
  print_check "AWS CLI installed ($aws_version)" "pass"
else
  print_check "AWS CLI not found - install with: pip install awscli" "fail"
fi

# Check 2: AWS Credentials
if aws sts get-caller-identity &> /dev/null; then
  account_id=$(aws sts get-caller-identity --query 'Account' --output text)
  principal=$(aws sts get-caller-identity --query 'Arn' --output text)
  print_check "AWS credentials configured (Account: $account_id)" "pass"
else
  print_check "AWS credentials not configured - run: aws configure" "fail"
fi

# Check 3: CDK CLI
echo ""
echo "📋 Checking CDK CLI..."
if command -v cdk &> /dev/null; then
  cdk_version=$(cdk --version)
  print_check "CDK CLI installed ($cdk_version)" "pass"
else
  print_check "CDK CLI not found - install with: npm install -g aws-cdk" "fail"
fi

# Check 4: Node.js
echo ""
echo "📋 Checking Node.js..."
if command -v node &> /dev/null; then
  node_version=$(node --version)
  print_check "Node.js installed ($node_version)" "pass"
else
  print_check "Node.js not found - install from nodejs.org" "fail"
fi

# Check 5: Python
echo ""
echo "📋 Checking Python..."
if command -v python3 &> /dev/null; then
  python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
  print_check "Python 3 installed (v$python_version)" "pass"
else
  print_check "Python 3 not found - install Python 3.11+" "fail"
fi

# Check 6: infrastructure directory
echo ""
echo "📋 Checking project structure..."
if [ -d "infrastructure" ]; then
  print_check "infrastructure/ directory exists" "pass"
else
  print_check "infrastructure/ directory not found" "fail"
fi

# Check 7: CDK stack file
if [ -f "infrastructure/lib/dctech-events-stack.ts" ]; then
  print_check "CDK stack file exists" "pass"
else
  print_check "CDK stack file not found" "fail"
fi

# Check 8: CDK config
if [ -f "infrastructure/lib/config.ts" ]; then
  print_check "CDK config file exists" "pass"
else
  print_check "CDK config file not found" "fail"
fi

# Check 9: GitHub workflow
if [ -f ".github/workflows/deploy.yml" ]; then
  print_check "GitHub Actions deployment workflow exists" "pass"
else
  print_check "GitHub Actions deployment workflow not found" "fail"
fi

# Check 10: Environment variables
echo ""
echo "📋 Checking environment variables..."
if [ -n "$HOSTED_ZONE_ID" ]; then
  print_check "HOSTED_ZONE_ID is set ($HOSTED_ZONE_ID)" "pass"
else
  print_check "HOSTED_ZONE_ID not set - required for Route53" "warn"
fi

if [ -n "$AWS_REGION" ]; then
  print_check "AWS_REGION is set ($AWS_REGION)" "pass"
else
  print_check "AWS_REGION not set - will use default (us-east-1)" "warn"
fi

# Check 11: Route53 Hosted Zone
echo ""
echo "📋 Checking Route53 hosted zone..."
if [ -n "$HOSTED_ZONE_ID" ]; then
  if aws route53 get-hosted-zone --id "$HOSTED_ZONE_ID" &> /dev/null; then
    zone_name=$(aws route53 get-hosted-zone --id "$HOSTED_ZONE_ID" --query 'HostedZone.Name' --output text)
    print_check "Route53 hosted zone exists ($zone_name)" "pass"
  else
    print_check "Route53 hosted zone ID is invalid or inaccessible" "fail"
  fi
else
  print_check "Cannot verify Route53 hosted zone - HOSTED_ZONE_ID not set" "warn"
fi

# Check 12: Git status
echo ""
echo "📋 Checking git status..."
if git rev-parse --git-dir > /dev/null 2>&1; then
  if git status --porcelain | grep -q .; then
    print_check "Git repository has uncommitted changes - commit before deploying" "warn"
  else
    print_check "Git repository is clean" "pass"
  fi
else
  print_check "Not in a git repository" "fail"
fi

# Check 13: NPM dependencies in infrastructure/
echo ""
echo "📋 Checking infrastructure dependencies..."
if [ -d "infrastructure/node_modules" ]; then
  print_check "NPM dependencies already installed in infrastructure/" "pass"
else
  print_check "NPM dependencies not installed - run: cd infrastructure && npm install" "warn"
fi

# Check 14: Make command (for site generation)
echo ""
echo "📋 Checking build commands..."
if command -v make &> /dev/null; then
  print_check "Make is installed (required for 'make all')" "pass"
else
  print_check "Make not found - required for site generation" "fail"
fi

# Check 15: Python requirements
if [ -f "requirements.txt" ]; then
  print_check "requirements.txt exists" "pass"
else
  print_check "requirements.txt not found" "fail"
fi

# Summary
echo ""
echo "================================================"
echo "📊 Readiness Check Summary"
echo "================================================"
echo -e "  ${COLOR_GREEN}Passed: $CHECKS_PASSED${COLOR_RESET}"
if [ $CHECKS_WARNING -gt 0 ]; then
  echo -e "  ${COLOR_YELLOW}Warnings: $CHECKS_WARNING${COLOR_RESET}"
fi
if [ $CHECKS_FAILED -gt 0 ]; then
  echo -e "  ${COLOR_RED}Failed: $CHECKS_FAILED${COLOR_RESET}"
  echo ""
  echo "❌ Deployment not ready. Fix the failures above before deploying."
  exit 1
fi

if [ $CHECKS_WARNING -gt 0 ]; then
  echo ""
  echo "⚠️  Some checks have warnings. Review and address before deploying."
fi

echo ""
echo "✅ Deployment readiness check passed!"
echo ""
echo "📚 Next steps:"
echo "  1. Review infrastructure/README.md for configuration options"
echo "  2. Run: cd infrastructure && npm install"
echo "  3. Run: npm run cdk synth (to review CloudFormation)"
echo "  4. Run: npm run cdk deploy (to deploy to AWS)"
echo "  5. Capture stack outputs for GitHub repository variables"
echo "  6. Configure GitHub Actions with repository variables"
echo ""
echo "For detailed instructions, see DEPLOYMENT_RUNBOOK.md"
