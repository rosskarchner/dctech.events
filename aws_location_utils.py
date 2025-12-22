#!/usr/bin/env python3
"""
AWS Places API v2 integration for address normalization.

This module provides address normalization using AWS Places API v2 (geo-places) with caching.
Falls back to the local normalize_address function when AWS credentials are not available.
"""

import os
import json
import boto3
from botocore.exceptions import NoCredentialsError, ClientError, PartialCredentialsError
from address_utils import normalize_address

# Cache file for location normalization results
CACHE_DIR = '_cache'
LOCATION_CACHE_FILE = os.path.join(CACHE_DIR, 'locations.json')

# Global cache dictionary
_location_cache = None


def _get_aws_config():
    """Get AWS configuration from environment variables."""
    return {
        'region': os.environ.get('AWS_REGION', 'us-east-1')
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


def _normalize_with_aws(address, places_client):
    """
    Normalize an address using AWS Places API v2.
    
    Args:
        address: The address string to normalize
        places_client: Boto3 geo-places client
        
    Returns:
        Normalized address string or None if the service fails
    """
    if not address or not isinstance(address, str):
        return None
    
    try:
        # Search for the place using AWS Places API v2
        response = places_client.search_text(
            QueryText=address,
            MaxResults=1
        )
        
        # Check if we got results
        if not response.get('ResultItems'):
            return None
        
        # Get the first (best) result
        result = response['ResultItems'][0]
        
        # Extract the formatted address label
        # In the new API, the address is in the 'Address' object with a 'Label' field
        address_obj = result.get('Address', {})
        label = address_obj.get('Label', '')
        
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
            print(f"AWS Places API error: {e}")
        return None
    except (NoCredentialsError, PartialCredentialsError):
        # Silently handle credential errors - these are logged at the higher level
        return None
    except Exception as e:
        print(f"Unexpected error in AWS Places API: {e}")
        return None


# Track whether we've logged AWS status to avoid spamming logs
_aws_status_logged = False

def normalize_address_with_aws(address):
    """
    Normalize an address using AWS Places API v2 with caching.
    Falls back to local normalization if AWS is not available.
    
    This function:
    1. Checks the cache for the exact address string
    2. If not cached, tries AWS Places API v2 (geo-places)
    3. Caches the AWS result (but never the fallback result)
    4. Falls back to local normalize_address if AWS is unavailable
    
    Args:
        address: The address string to normalize
        
    Returns:
        Normalized address string
    """
    global _aws_status_logged
    
    if not address or not isinstance(address, str):
        return address
    
    # Load the cache
    cache = _load_location_cache()
    
    # Check if we have a cached result for this exact address
    if address in cache:
        return cache[address]
    
    # Get AWS configuration
    aws_config = _get_aws_config()
    
    # Try to use AWS Places API v2
    aws_result = None
    aws_available = False
    try:
        places_client = boto3.client('geo-places', region_name=aws_config['region'])
        aws_result = _normalize_with_aws(address, places_client)
        aws_available = True
        
        # Log AWS API usage status (only once)
        if not _aws_status_logged:
            print("✓ Using AWS Places API v2 for address normalization")
            _aws_status_logged = True
            
    except NoCredentialsError:
        # AWS credentials not available, use fallback
        if not _aws_status_logged:
            print("⚠ AWS credentials not available - using local address normalization")
            _aws_status_logged = True
    except Exception as e:
        # Any other AWS setup error, use fallback
        if not _aws_status_logged:
            print(f"⚠ AWS Places API not available ({type(e).__name__}) - using local address normalization")
            _aws_status_logged = True
    
    # If AWS worked, cache and return the result
    if aws_result:
        cache[address] = aws_result
        _save_location_cache()
        return aws_result
    
    # Fall back to local normalization (don't cache fallback results)
    if aws_available and not aws_result:
        # AWS was available but didn't find a result - log it (truncate long addresses)
        print(f"  → AWS Places API: no result for '{address}' - using local normalization")
    
    return normalize_address(address)
