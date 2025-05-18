#!/usr/bin/env python3
"""
Verification script for ECR infrastructure changes.
"""

import yaml
import sys

def verify_ecr_infrastructure():
    """Verify that the ECR infrastructure template has been updated correctly."""
    try:
        with open("ecr-infrastructure.yaml", 'r') as file:
            template = yaml.safe_load(file)
    except Exception as e:
        print(f"Error loading template: {e}")
        return False
    
    # Check resources
    resources = template.get('Resources', {})
    if 'AppRepository' not in resources:
        print("ERROR: AppRepository resource is missing")
        return False
    
    if 'AggregatorRepository' not in resources:
        print("ERROR: AggregatorRepository resource is missing")
        return False
    
    if 'FrontendRepository' in resources:
        print("ERROR: FrontendRepository should be renamed to AppRepository")
        return False
    
    if 'AuthenticatedViewsRepository' in resources:
        print("ERROR: AuthenticatedViewsRepository should be removed")
        return False
    
    # Check repository names
    app_repo = resources.get('AppRepository', {})
    app_repo_name = app_repo.get('Properties', {}).get('RepositoryName')
    if app_repo_name != "cal-containers-app":
        print(f"ERROR: AppRepository name is incorrect: {app_repo_name}")
        return False
    
    aggregator_repo = resources.get('AggregatorRepository', {})
    aggregator_repo_name = aggregator_repo.get('Properties', {}).get('RepositoryName')
    if aggregator_repo_name != "cal-containers-aggregator":
        print(f"ERROR: AggregatorRepository name is incorrect: {aggregator_repo_name}")
        return False
    
    # Check outputs
    outputs = template.get('Outputs', {})
    required_outputs = ['AppRepositoryURI', 'AppRepositoryName',
                       'AggregatorRepositoryURI', 'AggregatorRepositoryName',
                       'GitHubActionsRoleARN', 'StackEnvironment']
    
    for output in required_outputs:
        if output not in outputs:
            print(f"ERROR: Output {output} is missing")
            return False
    
    if 'FrontendRepositoryURI' in outputs or 'FrontendRepositoryName' in outputs:
        print("ERROR: Frontend outputs should be renamed to App outputs")
        return False
    
    if 'AuthenticatedViewsRepositoryURI' in outputs or 'AuthenticatedViewsRepositoryName' in outputs:
        print("ERROR: AuthenticatedViews outputs should be removed")
        return False
    
    print("SUCCESS: ECR infrastructure template has been updated correctly!")
    return True

if __name__ == '__main__':
    success = verify_ecr_infrastructure()
    sys.exit(0 if success else 1)