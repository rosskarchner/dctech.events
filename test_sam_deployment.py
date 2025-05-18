#!/usr/bin/env python3
import os
import yaml
import unittest
import subprocess

class TestSAMDeployment(unittest.TestCase):
    """Test the SAM template and deployment script."""

    def test_template_exists(self):
        """Test that the SAM template exists."""
        self.assertTrue(os.path.exists('template.yaml'), "template.yaml file not found")

    def test_template_is_valid_yaml(self):
        """Test that the SAM template is valid YAML."""
        try:
            with open('template.yaml', 'r') as f:
                yaml.safe_load(f)
            self.assertTrue(True)
        except yaml.YAMLError as e:
            self.fail(f"template.yaml is not valid YAML: {e}")

    def test_template_has_required_sections(self):
        """Test that the SAM template has the required sections."""
        with open('template.yaml', 'r') as f:
            template = yaml.safe_load(f)
        
        self.assertIn('AWSTemplateFormatVersion', template, "Missing AWSTemplateFormatVersion")
        self.assertIn('Transform', template, "Missing Transform")
        self.assertIn('Description', template, "Missing Description")
        self.assertIn('Parameters', template, "Missing Parameters")
        self.assertIn('Resources', template, "Missing Resources")
        self.assertIn('Outputs', template, "Missing Outputs")

    def test_template_has_required_parameters(self):
        """Test that the SAM template has the required parameters."""
        with open('template.yaml', 'r') as f:
            template = yaml.safe_load(f)
        
        parameters = template.get('Parameters', {})
        self.assertIn('DomainName', parameters, "Missing DomainName parameter")
        self.assertIn('AuthDomainName', parameters, "Missing AuthDomainName parameter")
        self.assertIn('Environment', parameters, "Missing Environment parameter")
        
        # Verify that the old parameters are removed
        self.assertNotIn('AggregatorImageUri', parameters, "AggregatorImageUri parameter should be removed")
        self.assertNotIn('AppImageUri', parameters, "AppImageUri parameter should be removed")

    def test_template_has_required_resources(self):
        """Test that the SAM template has the required resources."""
        with open('template.yaml', 'r') as f:
            template = yaml.safe_load(f)
        
        resources = template.get('Resources', {})
        self.assertIn('AggregatorFunction', resources, "Missing AggregatorFunction resource")
        self.assertIn('AggregatorFunctionRole', resources, "Missing AggregatorFunctionRole resource")
        self.assertIn('StaticSiteGeneratorFunction', resources, "Missing StaticSiteGeneratorFunction resource")
        self.assertIn('ApiFunction', resources, "Missing ApiFunction resource")
        
        # Check that the functions use local Dockerfiles
        aggregator_function = resources.get('AggregatorFunction', {}).get('Properties', {})
        self.assertEqual(aggregator_function.get('PackageType'), 'Image', "AggregatorFunction should use Image package type")
        self.assertIn('Metadata', resources.get('AggregatorFunction', {}), "AggregatorFunction should have Metadata section")
        self.assertIn('Dockerfile', resources.get('AggregatorFunction', {}).get('Metadata', {}), "AggregatorFunction should specify Dockerfile")
        self.assertIn('DockerContext', resources.get('AggregatorFunction', {}).get('Metadata', {}), "AggregatorFunction should specify DockerContext")
        
        # Check that the AggregatorFunctionRole has the required properties
        aggregator_role = resources.get('AggregatorFunctionRole', {}).get('Properties', {})
        self.assertIn('AssumeRolePolicyDocument', aggregator_role, "AggregatorFunctionRole should have AssumeRolePolicyDocument")
        self.assertIn('ManagedPolicyArns', aggregator_role, "AggregatorFunctionRole should have ManagedPolicyArns")
        self.assertIn('Policies', aggregator_role, "AggregatorFunctionRole should have Policies")
        
        static_site_function = resources.get('StaticSiteGeneratorFunction', {}).get('Properties', {})
        self.assertEqual(static_site_function.get('PackageType'), 'Image', "StaticSiteGeneratorFunction should use Image package type")
        self.assertIn('Metadata', resources.get('StaticSiteGeneratorFunction', {}), "StaticSiteGeneratorFunction should have Metadata section")
        self.assertIn('Dockerfile', resources.get('StaticSiteGeneratorFunction', {}).get('Metadata', {}), "StaticSiteGeneratorFunction should specify Dockerfile")
        self.assertIn('DockerContext', resources.get('StaticSiteGeneratorFunction', {}).get('Metadata', {}), "StaticSiteGeneratorFunction should specify DockerContext")
        
        api_function = resources.get('ApiFunction', {}).get('Properties', {})
        self.assertEqual(api_function.get('PackageType'), 'Image', "ApiFunction should use Image package type")
        self.assertIn('Metadata', resources.get('ApiFunction', {}), "ApiFunction should have Metadata section")
        self.assertIn('Dockerfile', resources.get('ApiFunction', {}).get('Metadata', {}), "ApiFunction should specify Dockerfile")
        self.assertIn('DockerContext', resources.get('ApiFunction', {}).get('Metadata', {}), "ApiFunction should specify DockerContext")

    def test_deployment_script_exists(self):
        """Test that the deployment script exists."""
        self.assertTrue(os.path.exists('deploy.sh'), "deploy.sh file not found")

    def test_deployment_script_is_executable(self):
        """Test that the deployment script is executable."""
        self.assertTrue(os.access('deploy.sh', os.X_OK), "deploy.sh is not executable")

    def test_deployment_script_has_help_option(self):
        """Test that the deployment script has a help option."""
        try:
            result = subprocess.run(['./deploy.sh', '--help'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, "deploy.sh --help should exit with code 0")
            self.assertIn('Usage:', result.stdout, "deploy.sh --help should show usage information")
        except subprocess.SubprocessError as e:
            self.fail(f"Failed to run deploy.sh --help: {e}")

    def test_app_lambda_function_has_required_handlers(self):
        """Test that the app lambda_function.py has the required handlers."""
        self.assertTrue(os.path.exists('app/lambda_function.py'), "app/lambda_function.py file not found")
        
        with open('app/lambda_function.py', 'r') as f:
            content = f.read()
        
        self.assertIn('def lambda_handler(event, context):', content, "Missing lambda_handler function")
        self.assertIn('def static_site_generator_handler(event, context):', content, "Missing static_site_generator_handler function")
        self.assertIn('def api_handler(event, context):', content, "Missing api_handler function")

    def test_aggregator_lambda_function_has_required_handler(self):
        """Test that the aggregator lambda_function.py has the required handler."""
        self.assertTrue(os.path.exists('aggregator-lambda/lambda_function.py'), "aggregator-lambda/lambda_function.py file not found")
        
        with open('aggregator-lambda/lambda_function.py', 'r') as f:
            content = f.read()
        
        self.assertIn('def handler(event, context):', content, "Missing handler function")

if __name__ == '__main__':
    unittest.main()