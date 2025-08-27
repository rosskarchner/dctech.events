#!/usr/bin/env python3
"""
GitHub Copilot-powered validation script for DC Tech Events PR submissions.
Uses GitHub Copilot API to make nuanced decisions about event appropriateness.
Only validates single events, not groups.
"""

import os
import sys
import yaml
import requests
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# DC coordinates (White House)
DC_LAT = 38.8977
DC_LON = -77.0365
MAX_DISTANCE_MILES = 50

class CopilotEventValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []
        
        # GitHub token for Copilot API access
        self.github_token = os.environ.get('GITHUB_TOKEN')
        if not self.github_token:
            raise ValueError("GITHUB_TOKEN environment variable is required")
        
        self.copilot_api_base = "https://api.github.com/copilot"
        
    def validate_yaml_structure(self, file_path: str, content: str) -> Optional[Dict]:
        """Validate YAML structure and return parsed content."""
        try:
            data = yaml.safe_load(content)
            if not isinstance(data, dict):
                self.errors.append(f"{file_path}: YAML must contain a dictionary")
                return None
            return data
        except yaml.YAMLError as e:
            self.errors.append(f"{file_path}: Invalid YAML - {str(e)}")
            return None

    def validate_single_event(self, file_path: str, data: Dict) -> bool:
        """Validate a single event YAML file."""
        required_fields = ['title', 'date', 'time', 'url', 'location']
        
        # Check required fields
        for field in required_fields:
            if field not in data:
                self.errors.append(f"{file_path}: Missing required field '{field}'")
                return False

        # Validate date format and reasonableness
        try:
            event_date = datetime.strptime(data['date'], '%Y-%m-%d')
            if event_date < datetime.now() - timedelta(days=1):
                self.errors.append(f"{file_path}: Event date is in the past")
                return False
            if event_date > datetime.now() + timedelta(days=365):
                self.warnings.append(f"{file_path}: Event date is more than a year in the future")
        except ValueError:
            self.errors.append(f"{file_path}: Invalid date format, use YYYY-MM-DD")
            return False

        # Validate time format
        try:
            datetime.strptime(data['time'], '%H:%M')
        except ValueError:
            self.errors.append(f"{file_path}: Invalid time format, use HH:MM (24-hour)")
            return False

        # Validate URL accessibility
        if not self.validate_url(data['url']):
            self.errors.append(f"{file_path}: URL is not accessible")
            return False

        # Copilot-powered content validation
        if not self.copilot_validate_event_content(data['url'], data['title']):
            return False

        return True

    def validate_url(self, url: str) -> bool:
        """Check if URL is accessible."""
        try:
            response = requests.get(url, timeout=10, allow_redirects=True)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def copilot_validate_event_content(self, url: str, title: str) -> bool:
        """Use GitHub Copilot to validate event content appropriateness."""
        try:
            # Fetch content from URL
            content = ""
            try:
                response = requests.get(url, timeout=10)
                content = response.text[:3000]  # Limit content to avoid token limits
            except requests.RequestException:
                self.warnings.append(f"Could not fetch content from {url}, validating title only")
            
            # Create prompt for Copilot
            prompt = self._create_event_validation_prompt(title, content, url)
            
            # Call Copilot API
            response = self._call_copilot_api(prompt)
            
            if response:
                return self._process_copilot_response(response, "event")
            else:
                self.errors.append("Copilot validation failed and no fallback available")
                return False
                
        except Exception as e:
            self.errors.append(f"Copilot validation error: {str(e)}")
            return False

    def _create_event_validation_prompt(self, title: str, content: str, url: str) -> str:
        """Create a prompt for Copilot event validation."""
        return f"""You are validating whether an event should be included in a DC area technology events calendar.

Please analyze the following event and respond with a JSON object containing your assessment:

Event Title: {title}
Event URL: {url}
Event Content/Description: {content[:1500] if content else "No content available"}

Validation Criteria:
1. MUST be technology-related (software development, data science, cybersecurity, cloud computing, AI/ML, DevOps, etc.)
2. MUST NOT be paid training, certification courses, bootcamps, or commercial educational programs
3. SHOULD be community events, meetups, conferences, workshops, or similar gatherings
4. CAN be virtual, hybrid, or in-person (virtual-only is acceptable)
5. SHOULD be relevant to tech professionals, developers, or enthusiasts

Please respond with ONLY a JSON object in this exact format:
{{
    "is_appropriate": true/false,
    "is_tech_related": true/false,
    "is_paid_training": true/false,
    "is_community_event": true/false,
    "confidence_score": 0.0-1.0,
    "reasoning": "Brief explanation of your decision",
    "concerns": ["list", "of", "any", "concerns"]
}}

Be strict about paid training - if there are mentions of tuition, course fees, certification costs, enrollment, or similar commercial educational language, mark is_paid_training as true.
Be inclusive about technology topics - include emerging tech, tech business topics, and adjacent fields like UX/design when they're tech-focused."""

    def _call_copilot_api(self, prompt: str) -> Optional[str]:
        """Call GitHub Copilot API with the given prompt."""
        try:
            headers = {
                'Authorization': f'Bearer {self.github_token}',
                'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28'
            }
            
            # Use the chat completions endpoint
            data = {
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'model': 'gpt-4o',  # or whatever model is available
                'max_tokens': 1000,
                'temperature': 0.1  # Low temperature for consistent responses
            }
            
            response = requests.post(
                f'{self.copilot_api_base}/chat/completions',
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                self.warnings.append(f"Copilot API error: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            self.warnings.append(f"Copilot API request error: {str(e)}")
            return None
        except Exception as e:
            self.warnings.append(f"Unexpected error calling Copilot API: {str(e)}")
            return None

    def _process_copilot_response(self, response: str, validation_type: str) -> bool:
        """Process Copilot response and update errors/warnings."""
        try:
            # Extract JSON from response (in case there's extra text)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                self.warnings.append("Could not parse Copilot response as JSON")
                return False
            
            result = json.loads(json_match.group())
            
            # Validate required fields
            required_fields = ['is_appropriate', 'confidence_score', 'reasoning']
            if not all(field in result for field in required_fields):
                self.warnings.append("Copilot response missing required fields")
                return False
            
            # Check confidence score
            confidence = result.get('confidence_score', 0)
            if confidence < 0.7:
                self.warnings.append(f"Copilot validation has low confidence ({confidence:.2f}): {result.get('reasoning', 'No reason provided')}")
            
            # Process the decision
            if not result['is_appropriate']:
                reasoning = result.get('reasoning', 'No reason provided')
                concerns = result.get('concerns', [])
                
                error_msg = f"Copilot determined this {validation_type} is not appropriate: {reasoning}"
                if concerns:
                    error_msg += f" Concerns: {', '.join(concerns)}"
                
                self.errors.append(error_msg)
                return False
            
            # Check specific criteria for events
            if result.get('is_paid_training', False):
                self.errors.append("Copilot detected this appears to be paid training (not allowed)")
                return False
            if not result.get('is_tech_related', True):
                self.errors.append("Copilot determined this event is not technology-related")
                return False
            
            # Add any concerns as warnings
            concerns = result.get('concerns', [])
            for concern in concerns:
                self.warnings.append(f"Copilot concern: {concern}")
            
            return True
            
        except json.JSONDecodeError:
            self.warnings.append("Could not parse Copilot response as valid JSON")
            return False
        except Exception as e:
            self.warnings.append(f"Error processing Copilot response: {str(e)}")
            return False







def main():
    if len(sys.argv) != 2:
        print("Usage: python copilot_event_validator.py '<space-separated-file-list>'")
        sys.exit(1)

    changed_files = sys.argv[1].split()
    validator = CopilotEventValidator()
    
    all_valid = True
    
    for file_path in changed_files:
        if not os.path.exists(file_path):
            continue
            
        # Only validate single events
        if not file_path.startswith('_single_events/'):
            continue
            
        print(f"Validating {file_path} with GitHub Copilot...")
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Parse YAML
        data = validator.validate_yaml_structure(file_path, content)
        if data is None:
            all_valid = False
            continue
        
        # Validate single event
        if not validator.validate_single_event(file_path, data):
            all_valid = False
    
    # Post comment to PR if there are errors or warnings
    if validator.errors or validator.warnings:
        comment = "## GitHub Copilot-Powered Event Validation Results\n\n"
        
        if validator.errors:
            comment += "### ❌ Errors (must be fixed):\n"
            for error in validator.errors:
                comment += f"- {error}\n"
            comment += "\n"
        
        if validator.warnings:
            comment += "### ⚠️ Warnings:\n"
            for warning in validator.warnings:
                comment += f"- {warning}\n"
            comment += "\n"
        
        if all_valid:
            comment += "### ✅ All Copilot validations passed! This PR will be auto-merged."
        else:
            comment += "### Please fix the errors above before this PR can be merged."
            comment += "\n\n*This validation was performed using GitHub Copilot to make nuanced decisions about event appropriateness.*"
        
        # Post comment using GitHub CLI
        pr_number = os.environ.get('PR_NUMBER')
        if pr_number:
            with open('/tmp/copilot_comment.md', 'w') as f:
                f.write(comment)
            os.system(f'gh pr comment {pr_number} --body-file /tmp/copilot_comment.md')
    
    # Set output for GitHub Actions
    print(f"::set-output name=validation_passed::{str(all_valid).lower()}")
    
    if not all_valid:
        sys.exit(1)

if __name__ == "__main__":
    main()
