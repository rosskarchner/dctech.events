#!/usr/bin/env python3
"""
Test script to verify the ECR infrastructure template and deployment script.
"""

import os
import unittest
import subprocess
import yaml
import json


class TestECRInfrastructure(unittest.TestCase):
    """Test cases for ECR infrastructure template and deployment script."""

    def setUp(self):
        """Set up test environment."""
        self.template_file = "ecr-infrastructure.yaml"
        self.script_file = "deploy-ecr-infrastructure.sh"

    def test_template_file_exists(self):
        """Test that the CloudFormation template file exists."""
        self.assertTrue(os.path.isfile(self.template_file),
                        f"Template file {self.template_file} does not exist")

    def test_script_file_exists(self):
        """Test that the deployment script file exists."""
        self.assertTrue(os.path.isfile(self.script_file),
                        f"Script file {self.script_file} does not exist")

    def test_script_is_executable(self):
        """Test that the deployment script is executable."""
        self.assertTrue(os.access(self.script_file, os.X_OK),
                        f"Script file {self.script_file} is not executable")

    def test_template_yaml_valid(self):
        """Test that the CloudFormation template is valid YAML."""
        try:
            with open(self.template_file, 'r') as file:
                yaml.safe_load(file)
        except yaml.YAMLError as e:
            self.fail(f"Template file is not valid YAML: {e}")

    def test_template_has_required_sections(self):
        """Test that the CloudFormation template has required sections."""
        with open(self.template_file, 'r') as file:
            template = yaml.safe_load(file)
        
        self.assertIn('Parameters', template, "Template is missing Parameters section")
        self.assertIn('Resources', template, "Template is missing Resources section")
        self.assertIn('Outputs', template, "Template is missing Outputs section")

    def test_template_has_required_parameters(self):
        """Test that the CloudFormation template has required parameters."""
        with open(self.template_file, 'r') as file:
            template = yaml.safe_load(file)
        
        parameters = template.get('Parameters', {})
        required_params = ['GitHubOrg', 'GitHubRepo', 'GitHubBranch', 
                          'StackEnvironment', 'ImageRetentionCount']
        
        for param in required_params:
            self.assertIn(param, parameters, f"Template is missing parameter: {param}")

    def test_template_has_required_resources(self):
        """Test that the CloudFormation template has required resources."""
        with open(self.template_file, 'r') as file:
            template = yaml.safe_load(file)
        
        resources = template.get('Resources', {})
        required_resources = ['AppRepository', 'AggregatorRepository', 
                             'GitHubActionsRole', 'GitHubOIDCProvider']
        
        for resource in required_resources:
            self.assertIn(resource, resources, f"Template is missing resource: {resource}")

    def test_template_has_required_outputs(self):
        """Test that the CloudFormation template has required outputs."""
        with open(self.template_file, 'r') as file:
            template = yaml.safe_load(file)
        
        outputs = template.get('Outputs', {})
        required_outputs = ['AppRepositoryURI', 'AppRepositoryName',
                           'AggregatorRepositoryURI', 'AggregatorRepositoryName',
                           'GitHubActionsRoleARN', 'StackEnvironment']
        
        for output in required_outputs:
            self.assertIn(output, outputs, f"Template is missing output: {output}")

    def test_script_help_option(self):
        """Test that the deployment script has a help option."""
        try:
            result = subprocess.run([f"./{self.script_file}", "--help"], 
                                   capture_output=True, text=True, check=True)
            self.assertIn("Usage:", result.stdout, "Help message does not contain 'Usage:'")
            self.assertIn("Options:", result.stdout, "Help message does not contain 'Options:'")
            # Verify that environment option is not in help text
            self.assertNotIn("--environment", result.stdout, "Help message should not contain '--environment' option")
        except subprocess.CalledProcessError as e:
            self.fail(f"Script failed with --help option: {e}")
            
    def test_repository_names_are_correct(self):
        """Test that the ECR repository names are correct without environment suffix."""
        with open(self.template_file, 'r') as file:
            template = yaml.safe_load(file)
        
        resources = template.get('Resources', {})
        
        # Check App Repository name
        app_repo = resources.get('AppRepository', {})
        self.assertIn('Properties', app_repo, "AppRepository is missing Properties")
        self.assertIn('RepositoryName', app_repo.get('Properties', {}), 
                     "AppRepository is missing RepositoryName")
        self.assertEqual(app_repo.get('Properties', {}).get('RepositoryName'), 
                        "cal-containers-app", 
                        "AppRepository name should be 'cal-containers-app'")
        
        # Check Aggregator Repository name
        aggregator_repo = resources.get('AggregatorRepository', {})
        self.assertIn('Properties', aggregator_repo, "AggregatorRepository is missing Properties")
        self.assertIn('RepositoryName', aggregator_repo.get('Properties', {}), 
                     "AggregatorRepository is missing RepositoryName")
        self.assertEqual(aggregator_repo.get('Properties', {}).get('RepositoryName'), 
                        "cal-containers-aggregator", 
                        "AggregatorRepository name should be 'cal-containers-aggregator'")

    def test_repository_names_do_not_use_environment_suffix(self):
        """Test that the ECR repository names do not use environment suffix."""
        with open(self.template_file, 'r') as file:
            template_content = file.read()
        
        # Check that repository names don't use StackEnvironment parameter
        self.assertNotIn('!Sub "cal-containers-app-${StackEnvironment}"', template_content,
                        "App repository name should not use environment suffix")
        self.assertNotIn('!Sub "cal-containers-aggregator-${StackEnvironment}"', template_content,
                        "Aggregator repository name should not use environment suffix")
                        
    def test_stack_name_fixed(self):
        """Test that the stack name is always 'cal-containers-ecr-infra'."""
        # Read the script file
        with open(self.script_file, 'r') as file:
            script_content = file.read()
            
        # Check that the default stack name is set correctly
        self.assertIn('STACK_NAME="cal-containers-ecr-infra"', script_content, 
                     "Default stack name should be 'cal-containers-ecr-infra'")
        
        # Check that there's no code that modifies the stack name with environment suffix
        self.assertNotIn('STACK_NAME="${STACK_NAME}-${ENVIRONMENT}"', script_content,
                        "Script should not modify stack name with environment suffix")


if __name__ == '__main__':
    unittest.main()