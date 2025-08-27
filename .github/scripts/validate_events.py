#!/usr/bin/env python3
"""
Validation script for DC Tech Events PR submissions.
Validates YAML structure, content appropriateness, and location proximity to DC.
"""

import os
import sys
import yaml
import requests
import boto3
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# DC coordinates (White House)
DC_LAT = 38.8977
DC_LON = -77.0365
MAX_DISTANCE_MILES = 50

# Tech keywords that indicate legitimate tech events
TECH_KEYWORDS = [
    'programming', 'software', 'developer', 'coding', 'python', 'javascript', 'java',
    'data science', 'machine learning', 'ai', 'artificial intelligence', 'cybersecurity',
    'devops', 'cloud', 'aws', 'azure', 'kubernetes', 'docker', 'api', 'web development',
    'mobile development', 'blockchain', 'cryptocurrency', 'iot', 'internet of things',
    'tech talk', 'hackathon', 'meetup', 'user group', 'open source', 'github',
    'database', 'sql', 'nosql', 'frontend', 'backend', 'fullstack', 'agile', 'scrum'
]

# Keywords that indicate paid training (exclude these)
TRAINING_KEYWORDS = [
    'certification', 'training course', 'bootcamp', 'tuition', 'enroll', 'register now',
    'course fee', 'payment', 'paid training', 'professional development course',
    'certificate program', 'learn to code', 'coding bootcamp'
]

# Virtual-only keywords (reject these)
VIRTUAL_ONLY_KEYWORDS = [
    'virtual only', 'online only', 'remote only', 'webinar only', 'zoom only'
]

# Hybrid keywords (allow these)
HYBRID_KEYWORDS = [
    'hybrid', 'in-person and virtual', 'livestream available', 'remote option',
    'virtual attendance available', 'both in-person and online'
]

class EventValidator:
    def __init__(self):
        self.location_client = boto3.client('location')
        self.place_index = 'DCTechEventsIndex'  # You'll need to create this
        self.errors = []
        self.warnings = []

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

        # Check if event is tech-related and not paid training
        if not self.validate_tech_content(data['url'], data['title']):
            return False

        # Validate location
        if not self.validate_location(data['location']):
            return False

        return True

    def validate_group(self, file_path: str, data: Dict) -> bool:
        """Validate a group YAML file."""
        required_fields = ['name', 'website']
        
        # Check required fields
        for field in required_fields:
            if field not in data:
                self.errors.append(f"{file_path}: Missing required field '{field}'")
                return False

        # Must have either ical or rss
        if 'ical' not in data and 'rss' not in data:
            self.errors.append(f"{file_path}: Must have either 'ical' or 'rss' field")
            return False

        # Validate website URL
        if not self.validate_url(data['website']):
            self.errors.append(f"{file_path}: Website URL is not accessible")
            return False

        # Validate feed URL
        feed_url = data.get('ical') or data.get('rss')
        if not self.validate_url(feed_url):
            self.errors.append(f"{file_path}: Feed URL is not accessible")
            return False

        # Check if group is tech-related
        if not self.validate_tech_content(data['website'], data['name']):
            return False

        return True

    def validate_url(self, url: str) -> bool:
        """Check if URL is accessible."""
        try:
            response = requests.get(url, timeout=10, allow_redirects=True)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def validate_tech_content(self, url: str, title: str) -> bool:
        """Check if content is tech-related and not paid training."""
        try:
            response = requests.get(url, timeout=10)
            content = response.text.lower()
            title_lower = title.lower()
            
            # Check for virtual-only (reject unless hybrid)
            virtual_only = any(keyword in content or keyword in title_lower 
                             for keyword in VIRTUAL_ONLY_KEYWORDS)
            is_hybrid = any(keyword in content or keyword in title_lower 
                          for keyword in HYBRID_KEYWORDS)
            
            if virtual_only and not is_hybrid:
                self.errors.append(f"Event appears to be virtual-only (not allowed)")
                return False

            # Check for paid training indicators
            has_training_keywords = any(keyword in content or keyword in title_lower 
                                      for keyword in TRAINING_KEYWORDS)
            if has_training_keywords:
                self.errors.append(f"Event appears to be paid training (not allowed)")
                return False

            # Check for tech keywords
            has_tech_keywords = any(keyword in content or keyword in title_lower 
                                  for keyword in TECH_KEYWORDS)
            if not has_tech_keywords:
                self.errors.append(f"Event does not appear to be tech-related")
                return False

            return True

        except requests.RequestException:
            self.warnings.append(f"Could not fetch content from {url} for validation")
            # If we can't fetch content, we'll be more lenient and just check the title
            title_lower = title.lower()
            has_tech_keywords = any(keyword in title_lower for keyword in TECH_KEYWORDS)
            has_training_keywords = any(keyword in title_lower for keyword in TRAINING_KEYWORDS)
            
            if has_training_keywords:
                self.errors.append(f"Title suggests paid training (not allowed)")
                return False
            if not has_tech_keywords:
                self.errors.append(f"Title does not appear to be tech-related")
                return False
            
            return True

    def validate_location(self, location: str) -> bool:
        """Validate location is within 50 miles of DC using AWS Location Service."""
        try:
            # Try to geocode the location
            response = self.location_client.search_place_index_for_text(
                IndexName=self.place_index,
                Text=location,
                MaxResults=1
            )
            
            if not response['Results']:
                self.errors.append(f"Could not geocode location: {location}")
                return False

            result = response['Results'][0]
            place = result['Place']
            coordinates = place['Geometry']['Point']
            
            # Calculate distance from DC
            distance = self.calculate_distance(
                DC_LAT, DC_LON, 
                coordinates[1], coordinates[0]  # AWS returns [lon, lat]
            )
            
            if distance > MAX_DISTANCE_MILES:
                self.errors.append(f"Location '{location}' is {distance:.1f} miles from DC (max {MAX_DISTANCE_MILES} miles)")
                return False

            return True

        except Exception as e:
            # Fallback: check if location contains DC area keywords
            dc_keywords = [
                'washington', 'dc', 'd.c.', 'arlington', 'alexandria', 'bethesda',
                'rockville', 'silver spring', 'fairfax', 'reston', 'herndon',
                'tysons', 'vienna', 'falls church', 'college park', 'greenbelt'
            ]
            
            location_lower = location.lower()
            if any(keyword in location_lower for keyword in dc_keywords):
                self.warnings.append(f"Could not verify exact distance for '{location}', but appears to be in DC area")
                return True
            
            self.errors.append(f"Could not validate location '{location}' and no DC area keywords found")
            return False

    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in miles."""
        from math import radians, cos, sin, asin, sqrt
        
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        
        # Radius of earth in miles
        r = 3956
        return c * r

def main():
    if len(sys.argv) != 2:
        print("Usage: python validate_events.py '<space-separated-file-list>'")
        sys.exit(1)

    changed_files = sys.argv[1].split()
    validator = EventValidator()
    
    all_valid = True
    
    for file_path in changed_files:
        if not os.path.exists(file_path):
            continue
            
        print(f"Validating {file_path}...")
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Parse YAML
        data = validator.validate_yaml_structure(file_path, content)
        if data is None:
            all_valid = False
            continue
        
        # Validate based on file type
        if file_path.startswith('_single_events/'):
            if not validator.validate_single_event(file_path, data):
                all_valid = False
        elif file_path.startswith('_groups/'):
            if not validator.validate_group(file_path, data):
                all_valid = False
    
    # Post comment to PR if there are errors or warnings
    if validator.errors or validator.warnings:
        comment = "## Validation Results\n\n"
        
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
            comment += "### ✅ All validations passed! This PR will be auto-merged."
        else:
            comment += "### Please fix the errors above before this PR can be merged."
        
        # Post comment using GitHub CLI
        pr_number = os.environ.get('PR_NUMBER')
        if pr_number:
            with open('/tmp/comment.md', 'w') as f:
                f.write(comment)
            os.system(f'gh pr comment {pr_number} --body-file /tmp/comment.md')
    
    # Set output for GitHub Actions
    print(f"::set-output name=validation_passed::{str(all_valid).lower()}")
    
    if not all_valid:
        sys.exit(1)

if __name__ == "__main__":
    main()
