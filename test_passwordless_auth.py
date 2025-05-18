#!/usr/bin/env python3
"""
Test script to validate the passwordless authentication flow.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add the app directory to the path
sys.path.append('.')

class TestPasswordlessAuth(unittest.TestCase):
    """Test cases for passwordless authentication flow."""
    
    def test_auth_callback_template(self):
        """Test that the auth_callback.html template has the required elements for passwordless auth."""
        template_path = './app/templates/auth_callback.html'
        
        # Check if the template exists
        self.assertTrue(os.path.exists(template_path), "auth_callback.html does not exist")
        
        # Check if the template contains the required elements for passwordless auth
        with open(template_path, 'r') as f:
            template_content = f.read()
            required_elements = [
                'id="code-verification"',
                'id="verification-code"',
                'id="verify-button"',
                'function verifyCode(',
                'params.error === \'login_required\''
            ]
            
            for element in required_elements:
                self.assertIn(element, template_content, 
                             f"auth_callback.html is missing required element: {element}")
    
    def test_cognito_user_pool_config(self):
        """Test that the Cognito User Pool configuration in template.yaml has the required elements."""
        template_path = './template.yaml'
        
        # Check if the template exists
        self.assertTrue(os.path.exists(template_path), "template.yaml does not exist")
        
        # Check if the template contains the required elements for passwordless auth
        with open(template_path, 'r') as f:
            template_content = f.read()
            required_elements = [
                'AdminCreateUserConfig:',
                'AllowAdminCreateUserOnly: false',
                'UsernameConfiguration:',
                'CaseSensitive: false',
                'LambdaConfig:',
                'PreSignUp:',
                'DefineAuthChallenge:',
                'CreateAuthChallenge:',
                'VerifyAuthChallengeResponse:',
                'ALLOW_CUSTOM_AUTH',
                'PreventUserExistenceErrors: ENABLED'
            ]
            
            for element in required_elements:
                self.assertIn(element, template_content, 
                             f"template.yaml is missing required element: {element}")
    
    def test_cognito_lambda_triggers(self):
        """Test that the Cognito Lambda triggers are defined in template.yaml."""
        template_path = './template.yaml'
        
        # Check if the template exists
        self.assertTrue(os.path.exists(template_path), "template.yaml does not exist")
        
        # Check if the template contains the required Lambda triggers
        with open(template_path, 'r') as f:
            template_content = f.read()
            required_elements = [
                'CognitoPreSignUpLambda:',
                'CognitoDefineAuthChallengeLambda:',
                'CognitoCreateAuthChallengeLambda:',
                'CognitoVerifyAuthChallengeLambda:',
                'autoConfirmUser = true',
                'autoVerifyEmail = true',
                'event.request.userNotFound',
                'challengeName = \'CUSTOM_CHALLENGE\'',
                'const code = crypto.randomInt(100000, 999999).toString()',
                'event.response.answerCorrect = (expectedCode === providedCode)'
            ]
            
            for element in required_elements:
                self.assertIn(element, template_content, 
                             f"template.yaml is missing required Lambda trigger element: {element}")

if __name__ == "__main__":
    unittest.main()