#!/usr/bin/env python3
"""
Test script for GitHub Copilot-powered event validation.
Run this locally to test the validation system.
"""

import sys
import os
sys.path.append('.github/scripts')

from copilot_event_validator import CopilotEventValidator
from copilot_cli_validator import CopilotCLIValidator

def test_event_validation():
    """Test event validation with sample data."""
    
    # Sample event data
    test_events = [
        {
            "title": "Python Meetup: Machine Learning Workshop",
            "url": "https://www.meetup.com/python-meetup/events/123456789/",
            "description": "Join us for a hands-on workshop on machine learning with Python. We'll cover scikit-learn, pandas, and more!"
        },
        {
            "title": "Certified AWS Solutions Architect Bootcamp - $2999",
            "url": "https://example-training.com/aws-bootcamp",
            "description": "Get certified in 5 days! Our intensive bootcamp includes exam voucher and guaranteed pass. Enroll now for $2999."
        },
        {
            "title": "DC JavaScript User Group Monthly Meeting",
            "url": "https://www.meetup.com/dc-js/events/987654321/",
            "description": "Monthly meeting of the DC JavaScript community. This month: React 18 features and performance optimization."
        }
    ]
    
    print("Testing Copilot Event Validation")
    print("=" * 50)
    
    # Test API method if available
    try:
        print("\n🤖 Testing Copilot API method...")
        validator = CopilotEventValidator()
        
        for i, event in enumerate(test_events, 1):
            print(f"\nTest Event {i}: {event['title']}")
            print("-" * 40)
            
            # Reset errors/warnings for each test
            validator.errors = []
            validator.warnings = []
            
            result = validator.copilot_validate_event_content(event['url'], event['title'])
            
            print(f"✅ Passed: {result}")
            if validator.errors:
                print("❌ Errors:")
                for error in validator.errors:
                    print(f"  - {error}")
            if validator.warnings:
                print("⚠️ Warnings:")
                for warning in validator.warnings:
                    print(f"  - {warning}")
                    
    except Exception as e:
        print(f"❌ Copilot API method failed: {str(e)}")
        
        # Try CLI method
        try:
            print("\n🖥️ Testing Copilot CLI method...")
            cli_validator = CopilotCLIValidator()
            
            for i, event in enumerate(test_events, 1):
                print(f"\nTest Event {i}: {event['title']}")
                print("-" * 40)
                
                # Reset errors/warnings for each test
                cli_validator.errors = []
                cli_validator.warnings = []
                
                result = cli_validator.copilot_validate_event_content(event['url'], event['title'])
                
                print(f"✅ Passed: {result}")
                if cli_validator.errors:
                    print("❌ Errors:")
                    for error in cli_validator.errors:
                        print(f"  - {error}")
                if cli_validator.warnings:
                    print("⚠️ Warnings:")
                    for warning in cli_validator.warnings:
                        print(f"  - {warning}")
                        
        except Exception as e:
            print(f"❌ Copilot CLI method also failed: {str(e)}")
            print("\n💡 Make sure you have:")
            print("  1. GitHub CLI installed: https://cli.github.com/")
            print("  2. GitHub Copilot enabled on your account")
            print("  3. Authenticated with 'gh auth login'")

if __name__ == "__main__":
    print("🚀 DC Tech Events - Copilot Event Validation Test")
    print("This script tests the AI-powered validation system for single events only.")
    print("\nNote: This requires GitHub Copilot access and may make API calls.")
    
    response = input("\nProceed with testing? (y/N): ")
    if response.lower() in ['y', 'yes']:
        test_event_validation()
        
        print("\n" + "=" * 50)
        print("✅ Testing complete!")
        print("\n💡 Next steps:")
        print("  1. Review the results above")
        print("  2. Adjust prompts in the validator scripts if needed")
        print("  3. Test with a real PR to see it in action")
        print("  4. Groups will now require manual review (no automation)")
    else:
        print("Testing cancelled.")
