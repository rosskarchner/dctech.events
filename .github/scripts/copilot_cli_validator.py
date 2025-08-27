#!/usr/bin/env python3
"""
GitHub Copilot CLI-based validation script for DC Tech Events PR submissions.
Uses `gh copilot` CLI command to make nuanced decisions about event appropriateness.
Only validates single events, not groups.
"""

import os
import sys
import yaml
import requests
import subprocess
import json
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class CopilotCLIValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []
        
        # Check if gh copilot is available
        try:
            result = subprocess.run(['gh', 'copilot', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                raise Exception("gh copilot not available")
        except Exception as e:
            raise Exception(f"GitHub Copilot CLI not available: {str(e)}")

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
        """Use GitHub Copilot CLI to validate event content appropriateness."""
        try:
            # Fetch content from URL
            content = ""
            try:
                response = requests.get(url, timeout=10)
                content = response.text[:2000]  # Limit content
            except requests.RequestException:
                self.warnings.append(f"Could not fetch content from {url}, validating title only")
            
            # Create prompt for Copilot
            prompt = self._create_event_validation_prompt(title, content, url)
            
            # Call Copilot CLI
            response = self._call_copilot_cli(prompt)
            
            if response:
                return self._process_copilot_response(response, "event")
            else:
                # Fallback to basic validation if Copilot fails
                self.warnings.append("Copilot validation failed, using fallback validation")
                return self._fallback_event_validation(title, content)
                
        except Exception as e:
            self.warnings.append(f"Copilot validation error: {str(e)}, using fallback")
            return self._fallback_event_validation(title, content if 'content' in locals() else "")

    def _create_event_validation_prompt(self, title: str, content: str, url: str) -> str:
        """Create a prompt for Copilot event validation."""
        return f"""Analyze this event for a DC tech events calendar. Respond with JSON only.

Event: {title}
URL: {url}
Content: {content[:1000] if content else "No content"}

Criteria:
- MUST be tech-related (programming, data science, AI, cybersecurity, etc.)
- MUST NOT be paid training/bootcamps/certification courses
- SHOULD be community events, meetups, conferences
- Virtual/hybrid/in-person all OK

Respond with JSON:
{{
    "is_appropriate": true/false,
    "is_tech_related": true/false,
    "is_paid_training": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}"""

    def _call_copilot_cli(self, prompt: str) -> Optional[str]:
        """Call GitHub Copilot CLI with the given prompt."""
        try:
            # Write prompt to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt)
                prompt_file = f.name
            
            try:
                # Call gh copilot suggest with the prompt
                result = subprocess.run([
                    'gh', 'copilot', 'suggest', 
                    '--type', 'shell',
                    '--prompt-file', prompt_file
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    return result.stdout.strip()
                else:
                    self.warnings.append(f"Copilot CLI error: {result.stderr}")
                    return None
                    
            finally:
                # Clean up temp file
                os.unlink(prompt_file)
                
        except subprocess.TimeoutExpired:
            self.warnings.append("Copilot CLI timeout")
            return None
        except Exception as e:
            self.warnings.append(f"Copilot CLI error: {str(e)}")
            return None

    def _process_copilot_response(self, response: str, validation_type: str) -> bool:
        """Process Copilot response and update errors/warnings."""
        try:
            # Try to extract JSON from the response
            import re
            json_match = re.search(r'\{[^}]*\}', response, re.DOTALL)
            if not json_match:
                self.warnings.append("Could not find JSON in Copilot response")
                return False
            
            result = json.loads(json_match.group())
            
            # Check if appropriate
            if not result.get('is_appropriate', False):
                reasoning = result.get('reasoning', 'No reason provided')
                self.errors.append(f"Copilot determined this {validation_type} is not appropriate: {reasoning}")
                return False
            
            # Check specific criteria for events
            if result.get('is_paid_training', False):
                self.errors.append("Copilot detected this appears to be paid training (not allowed)")
                return False
            if not result.get('is_tech_related', True):
                self.errors.append("Copilot determined this event is not technology-related")
                return False
            
            # Check confidence
            confidence = result.get('confidence', 0)
            if confidence < 0.7:
                self.warnings.append(f"Copilot has low confidence ({confidence:.2f}) in this assessment")
            
            return True
            
        except json.JSONDecodeError:
            self.warnings.append("Could not parse Copilot response as JSON")
            return False
        except Exception as e:
            self.warnings.append(f"Error processing Copilot response: {str(e)}")
            return False

    def _fallback_event_validation(self, title: str, content: str) -> bool:
        """Fallback validation using simple keyword matching."""
        tech_keywords = ['programming', 'software', 'developer', 'coding', 'tech', 'meetup']
        training_keywords = ['certification', 'bootcamp', 'tuition', 'course fee']
        
        text = (title + " " + content).lower()
        
        if any(keyword in text for keyword in training_keywords):
            self.errors.append("Appears to be paid training (fallback validation)")
            return False
        
        if not any(keyword in text for keyword in tech_keywords):
            self.errors.append("Does not appear to be tech-related (fallback validation)")
            return False
        
        return True

def main():
    if len(sys.argv) != 2:
        print("Usage: python copilot_cli_validator.py '<space-separated-file-list>'")
        sys.exit(1)

    changed_files = sys.argv[1].split()
    validator = CopilotCLIValidator()
    
    all_valid = True
    
    for file_path in changed_files:
        if not os.path.exists(file_path):
            continue
            
        # Only validate single events
        if not file_path.startswith('_single_events/'):
            continue
            
        print(f"Validating {file_path} with GitHub Copilot CLI...")
        
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
    
    # Output results
    if validator.errors or validator.warnings:
        print("## GitHub Copilot CLI Event Validation Results")
        
        if validator.errors:
            print("\n### ❌ Errors:")
            for error in validator.errors:
                print(f"- {error}")
        
        if validator.warnings:
            print("\n### ⚠️ Warnings:")
            for warning in validator.warnings:
                print(f"- {warning}")
    
    if not all_valid:
        sys.exit(1)

if __name__ == "__main__":
    main()
