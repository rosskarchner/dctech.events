#!/usr/bin/env python3
"""
Test that the deploy workflow has the correct step order.

This test ensures that track_events.py runs BEFORE the static site is frozen
to prevent discrepancies between event counts in the daily summary and the
/just-added/ page.
"""
import yaml
import pytest


def test_track_events_runs_before_freeze():
    """
    Verify that 'Track events' step comes before 'Generate static site' step.
    
    This is critical because:
    1. 'Generate static site' (make all) includes freeze.py which reads S3 metadata
    2. 'Track events' updates the S3 metadata with newly detected events
    3. If track_events runs after freeze, the frozen page will have stale counts
    """
    # Load the deploy workflow
    with open('.github/workflows/deploy.yml', 'r') as f:
        workflow = yaml.safe_load(f)
    
    # Get the build-and-deploy job steps
    steps = workflow['jobs']['build-and-deploy']['steps']
    
    # Find the indices of the relevant steps
    track_events_index = None
    generate_site_index = None
    
    for i, step in enumerate(steps):
        step_name = step.get('name', '')
        if 'Track events' in step_name:
            track_events_index = i
        elif 'Generate static site' in step_name:
            generate_site_index = i
    
    # Verify both steps exist
    assert track_events_index is not None, \
        "Could not find 'Track events and persist to S3' step in deploy workflow"
    assert generate_site_index is not None, \
        "Could not find 'Generate static site' step in deploy workflow"
    
    # Verify track_events comes BEFORE generate_site
    assert track_events_index < generate_site_index, \
        f"'Track events' (step {track_events_index}) must run BEFORE " \
        f"'Generate static site' (step {generate_site_index}) to ensure " \
        f"consistent event counts between daily summary and /just-added/ page"


def test_track_events_runs_after_aws_credentials():
    """
    Verify that 'Track events' runs after AWS credentials are configured.
    
    This is necessary because track_events.py needs AWS credentials to
    access S3.
    """
    # Load the deploy workflow
    with open('.github/workflows/deploy.yml', 'r') as f:
        workflow = yaml.safe_load(f)
    
    # Get the build-and-deploy job steps
    steps = workflow['jobs']['build-and-deploy']['steps']
    
    # Find the indices of the relevant steps
    track_events_index = None
    aws_config_index = None
    
    for i, step in enumerate(steps):
        step_name = step.get('name', '')
        if 'Track events' in step_name:
            track_events_index = i
        elif 'Configure AWS credentials' in step_name:
            aws_config_index = i
    
    # Verify both steps exist
    assert track_events_index is not None, \
        "Could not find 'Track events and persist to S3' step in deploy workflow"
    assert aws_config_index is not None, \
        "Could not find 'Configure AWS credentials' step in deploy workflow"
    
    # Verify AWS config comes BEFORE track_events
    assert aws_config_index < track_events_index, \
        f"'Configure AWS credentials' (step {aws_config_index}) must run BEFORE " \
        f"'Track events' (step {track_events_index}) to provide S3 access"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
