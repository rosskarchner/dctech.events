#!/usr/bin/env python3
"""
Setup script for AWS Location Service place index.
Run this once to create the required AWS resources.
"""

import boto3
import json

def setup_location_service():
    """Create the place index for geocoding."""
    client = boto3.client('location')
    
    place_index_name = 'DCTechEventsIndex'
    
    try:
        # Check if place index already exists
        response = client.describe_place_index(IndexName=place_index_name)
        print(f"Place index '{place_index_name}' already exists.")
        return
    except client.exceptions.ResourceNotFoundException:
        pass
    
    # Create place index
    try:
        response = client.create_place_index(
            IndexName=place_index_name,
            DataSource='Esri',  # Free tier available
            Description='Place index for DC Tech Events validation',
            PricingPlan='RequestBasedUsage'
        )
        print(f"Created place index '{place_index_name}' successfully.")
        print(f"ARN: {response['PlaceIndexArn']}")
    except Exception as e:
        print(f"Error creating place index: {e}")
        return

def create_iam_policy():
    """Generate IAM policy JSON for the required permissions."""
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "geo:SearchPlaceIndexForText"
                ],
                "Resource": "arn:aws:geo:*:*:place-index/DCTechEventsIndex"
            }
        ]
    }
    
    print("\nIAM Policy JSON (attach this to your GitHub Actions user):")
    print(json.dumps(policy, indent=2))

if __name__ == "__main__":
    print("Setting up AWS Location Service for DC Tech Events validation...")
    setup_location_service()
    create_iam_policy()
    
    print("\nNext steps:")
    print("1. Create an IAM user for GitHub Actions")
    print("2. Attach the above policy to that user")
    print("3. Generate access keys for the user")
    print("4. Add AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY as GitHub secrets")
    print("5. The validation workflow is ready to use!")
