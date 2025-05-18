#!/usr/bin/env python3
"""
Script to verify that the fix for the ECR infrastructure is correct.
"""

import os
import sys
import yaml

def verify_fix():
    """Verify that the fix for the ECR infrastructure is correct."""
    script_file = "deploy-ecr-infrastructure.sh"
    template_file = "ecr-infrastructure.yaml"
    
    # Check if the files exist
    if not os.path.isfile(script_file):
        print(f"Error: Script file {script_file} does not exist")
        return False
    
    if not os.path.isfile(template_file):
        print(f"Error: Template file {template_file} does not exist")
        return False
    
    # Read the script file
    with open(script_file, 'r') as file:
        script_content = file.read()
    
    # Check that the default stack name is set correctly
    if 'STACK_NAME="cal-containers-ecr-infra"' not in script_content:
        print("Error: Default stack name is not set to 'cal-containers-ecr-infra'")
        return False
    
    # Read the template file
    try:
        with open(template_file, 'r') as file:
            template = yaml.safe_load(file)
    except Exception as e:
        print(f"Error loading template: {e}")
        return False
    
    # Check resources
    resources = template.get('Resources', {})
    if 'AppRepository' not in resources:
        print("Error: AppRepository resource is missing")
        return False
    
    if 'AggregatorRepository' not in resources:
        print("Error: AggregatorRepository resource is missing")
        return False
    
    if 'FrontendRepository' in resources:
        print("Error: FrontendRepository should be renamed to AppRepository")
        return False
    
    if 'AuthenticatedViewsRepository' in resources:
        print("Error: AuthenticatedViewsRepository should be removed")
        return False
    
    # Check repository names
    app_repo = resources.get('AppRepository', {})
    app_repo_name = app_repo.get('Properties', {}).get('RepositoryName')
    if app_repo_name != "cal-containers-app":
        print(f"Error: AppRepository name is incorrect: {app_repo_name}")
        return False
    
    aggregator_repo = resources.get('AggregatorRepository', {})
    aggregator_repo_name = aggregator_repo.get('Properties', {}).get('RepositoryName')
    if aggregator_repo_name != "cal-containers-aggregator":
        print(f"Error: AggregatorRepository name is incorrect: {aggregator_repo_name}")
        return False
    
    # Check outputs
    outputs = template.get('Outputs', {})
    required_outputs = ['AppRepositoryURI', 'AppRepositoryName',
                       'AggregatorRepositoryURI', 'AggregatorRepositoryName',
                       'GitHubActionsRoleARN', 'StackEnvironment']
    
    for output in required_outputs:
        if output not in outputs:
            print(f"Error: Output {output} is missing")
            return False
    
    if 'FrontendRepositoryURI' in outputs or 'FrontendRepositoryName' in outputs:
        print("Error: Frontend outputs should be renamed to App outputs")
        return False
    
    if 'AuthenticatedViewsRepositoryURI' in outputs or 'AuthenticatedViewsRepositoryName' in outputs:
        print("Error: AuthenticatedViews outputs should be removed")
        return False
    
    print("Success: The ECR infrastructure has been updated correctly!")
    return True

if __name__ == '__main__':
    success = verify_fix()
    sys.exit(0 if success else 1)