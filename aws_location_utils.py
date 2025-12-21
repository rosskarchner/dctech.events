#!/usr/bin/env python3
"""
AWS Location Services integration for address normalization.

This module provides address normalization using AWS Location Services with caching.
Falls back to the local normalize_address function when AWS credentials are not available.
"""

import os
import json
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from address_utils import normalize_address

# Cache file for location normalization results
CACHE_DIR = '_cache'
LOCATION_CACHE_FILE = os.path.join(CACHE_DIR, 'locations.json')

# Global cache dictionary
_location_cache = None


def _get_aws_config():
    """Get AWS configuration from environment variables."""
    return {
        'region': os.environ.get('AWS_REGION', 'us-east-1'),
        'index_name': os.environ.get('AWS_LOCATION_INDEX_NAME', '')
    }


def _load_location_cache():
    """Load the location cache from disk."""
    global _location_cache
    if _location_cache is not None:
        return _location_cache
    
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    if os.path.exists(LOCATION_CACHE_FILE):
        try:
            with open(LOCATION_CACHE_FILE, 'r') as f:
                _location_cache = json.load(f)
        except Exception:
            _location_cache = {}
    else:
        _location_cache = {}
    
    return _location_cache


def _save_location_cache():
    """Save the location cache to disk."""
    global _location_cache
    if _location_cache is None:
        return
    
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    try:
        with open(LOCATION_CACHE_FILE, 'w') as f:
            json.dump(_location_cache, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to save location cache: {e}")


def _normalize_with_aws(address, location_client, index_name):
    """
    Normalize an address using AWS Location Services.
    
    Args:
        address: The address string to normalize
        location_client: Boto3 Location Services client
        index_name: Name of the AWS Location Services place index
        
    Returns:
        Normalized address string or None if the service fails
    """
    if not address or not isinstance(address, str):
        return None
    
    if not index_name:
        return None
    
    try:
        # Search for the place using AWS Location Services
        response = location_client.search_place_index_for_text(
            IndexName=index_name,
            Text=address,
            MaxResults=1
        )
        
        # Check if we got results
        if not response.get('Results'):
            return None
        
        # Get the first (best) result
        result = response['Results'][0]
        place = result.get('Place', {})
        
        # Extract the label (formatted address)
        label = place.get('Label', '')
        
        if label:
            # Apply basic normalization to AWS result
            # Remove zip codes and country names like the local normalizer does
            normalized = normalize_address(label)
            return normalized
        
        return None
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        # Don't print error for common expected cases
        if error_code not in ['ResourceNotFoundException', 'AccessDeniedException']:
            print(f"AWS Location Services error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error in AWS Location Services: {e}")
        return None


def normalize_address_with_aws(address):
    """
    Normalize an address using AWS Location Services with caching.
    Falls back to local normalization if AWS is not available.
    
    This function:
    1. Checks the cache for the exact address string
    2. If not cached, tries AWS Location Services
    3. Caches the AWS result (but never the fallback result)
    4. Falls back to local normalize_address if AWS is unavailable
    
    Args:
        address: The address string to normalize
        
    Returns:
        Normalized address string
    """
    if not address or not isinstance(address, str):
        return address
    
    # Load the cache
    cache = _load_location_cache()
    
    # Check if we have a cached result for this exact address
    if address in cache:
        return cache[address]
    
    # Get AWS configuration
    aws_config = _get_aws_config()
    
    # Try to use AWS Location Services
    aws_result = None
    try:
        location_client = boto3.client('location', region_name=aws_config['region'])
        aws_result = _normalize_with_aws(address, location_client, aws_config['index_name'])
    except NoCredentialsError:
        # AWS credentials not available, use fallback
        pass
    except Exception:
        # Any other AWS setup error, use fallback
        pass
    
    # If AWS worked, cache and return the result
    if aws_result:
        cache[address] = aws_result
        _save_location_cache()
        return aws_result
    
    # Fall back to local normalization (don't cache fallback results)
    return normalize_address(address)
