#!/usr/bin/env python3
"""
Validation script for all existing events and groups in the repository.
Use this to audit your current content and identify any issues.
"""

import os
import glob
import sys
from validate_events import EventValidator

def validate_all_files():
    """Validate all existing YAML files in _groups and _single_events directories."""
    validator = EventValidator()
    
    # Find all YAML files
    group_files = glob.glob('_groups/*.yml') + glob.glob('_groups/*.yaml')
    event_files = glob.glob('_single_events/*.yml') + glob.glob('_single_events/*.yaml')
    
    all_files = group_files + event_files
    
    if not all_files:
        print("No YAML files found in _groups/ or _single_events/ directories")
        return
    
    print(f"Found {len(group_files)} group files and {len(event_files)} event files")
    print("=" * 60)
    
    valid_count = 0
    invalid_count = 0
    
    # Track issues by category
    issues_by_category = {
        'yaml_errors': [],
        'missing_fields': [],
        'url_errors': [],
        'location_errors': [],
        'content_errors': [],
        'date_errors': []
    }
    
    for file_path in sorted(all_files):
        print(f"\nValidating {file_path}...")
        
        # Reset validator state for each file
        validator.errors = []
        validator.warnings = []
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
        except Exception as e:
            print(f"  ❌ Could not read file: {e}")
            invalid_count += 1
            continue
        
        # Parse YAML
        data = validator.validate_yaml_structure(file_path, content)
        if data is None:
            print(f"  ❌ YAML parsing failed")
            issues_by_category['yaml_errors'].append(file_path)
            invalid_count += 1
            continue
        
        # Validate based on file type
        is_valid = False
        if file_path.startswith('_single_events/'):
            is_valid = validator.validate_single_event(file_path, data)
        elif file_path.startswith('_groups/'):
            is_valid = validator.validate_group(file_path, data)
        
        # Categorize errors
        for error in validator.errors:
            if 'Missing required field' in error:
                issues_by_category['missing_fields'].append(f"{file_path}: {error}")
            elif 'URL is not accessible' in error or 'not accessible' in error:
                issues_by_category['url_errors'].append(f"{file_path}: {error}")
            elif 'location' in error.lower() or 'miles from DC' in error:
                issues_by_category['location_errors'].append(f"{file_path}: {error}")
            elif 'training' in error or 'tech-related' in error or 'virtual-only' in error:
                issues_by_category['content_errors'].append(f"{file_path}: {error}")
            elif 'date' in error.lower():
                issues_by_category['date_errors'].append(f"{file_path}: {error}")
        
        if is_valid:
            print(f"  ✅ Valid")
            if validator.warnings:
                print(f"  ⚠️  Warnings:")
                for warning in validator.warnings:
                    print(f"     - {warning}")
            valid_count += 1
        else:
            print(f"  ❌ Invalid")
            for error in validator.errors:
                print(f"     - {error}")
            invalid_count += 1
    
    # Summary report
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total files: {len(all_files)}")
    print(f"Valid: {valid_count}")
    print(f"Invalid: {invalid_count}")
    print(f"Success rate: {valid_count/len(all_files)*100:.1f}%")
    
    # Detailed breakdown by issue type
    print("\nISSUES BY CATEGORY:")
    print("-" * 30)
    
    for category, issues in issues_by_category.items():
        if issues:
            category_name = category.replace('_', ' ').title()
            print(f"\n{category_name} ({len(issues)} files):")
            for issue in issues[:10]:  # Show first 10 issues
                print(f"  - {issue}")
            if len(issues) > 10:
                print(f"  ... and {len(issues) - 10} more")
    
    # Recommendations
    print("\nRECOMMENDations:")
    print("-" * 15)
    
    if issues_by_category['url_errors']:
        print("• Check and update broken URLs")
    
    if issues_by_category['location_errors']:
        print("• Review events outside DC area or with unclear locations")
    
    if issues_by_category['content_errors']:
        print("• Remove paid training events and ensure tech focus")
    
    if issues_by_category['date_errors']:
        print("• Update past events or fix date formats")
    
    if issues_by_category['missing_fields']:
        print("• Add missing required fields to YAML files")
    
    # Generate cleanup script suggestions
    if invalid_count > 0:
        print(f"\nTo clean up invalid files, you might want to:")
        print("1. Review and fix the issues listed above")
        print("2. Remove outdated events (past dates)")
        print("3. Update broken URLs")
        print("4. Remove non-tech or paid training events")
        print("5. Re-run this script to verify fixes")

def generate_cleanup_report():
    """Generate a detailed report for manual cleanup."""
    validator = EventValidator()
    
    # Find all files
    group_files = glob.glob('_groups/*.yml') + glob.glob('_groups/*.yaml')
    event_files = glob.glob('_single_events/*.yml') + glob.glob('_single_events/*.yaml')
    
    report_lines = []
    report_lines.append("# DC Tech Events - Validation Report")
    report_lines.append(f"Generated on: {validator.errors}")  # Will be replaced with actual date
    report_lines.append("")
    
    # Process each file
    for file_path in sorted(group_files + event_files):
        validator.errors = []
        validator.warnings = []
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            data = validator.validate_yaml_structure(file_path, content)
            if data is None:
                continue
            
            if file_path.startswith('_single_events/'):
                is_valid = validator.validate_single_event(file_path, data)
            elif file_path.startswith('_groups/'):
                is_valid = validator.validate_group(file_path, data)
            
            if not is_valid or validator.warnings:
                report_lines.append(f"## {file_path}")
                if not is_valid:
                    report_lines.append("**Status: ❌ INVALID**")
                    report_lines.append("**Errors:**")
                    for error in validator.errors:
                        report_lines.append(f"- {error}")
                else:
                    report_lines.append("**Status: ✅ Valid**")
                
                if validator.warnings:
                    report_lines.append("**Warnings:**")
                    for warning in validator.warnings:
                        report_lines.append(f"- {warning}")
                
                report_lines.append("")
        
        except Exception as e:
            report_lines.append(f"## {file_path}")
            report_lines.append(f"**Status: ❌ ERROR**")
            report_lines.append(f"- Could not process file: {e}")
            report_lines.append("")
    
    # Write report
    with open('validation_report.md', 'w') as f:
        f.write('\n'.join(report_lines))
    
    print("Detailed report saved to: validation_report.md")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate all existing events and groups')
    parser.add_argument('--report', action='store_true', 
                       help='Generate detailed markdown report')
    parser.add_argument('--summary-only', action='store_true',
                       help='Show only summary statistics')
    
    args = parser.parse_args()
    
    if args.report:
        generate_cleanup_report()
    else:
        validate_all_files()
