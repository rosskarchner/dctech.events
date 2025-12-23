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
    # Default to DC/Northern Virginia area if no location bias specified
    # This improves results for local event addresses
    default_lat = 38.8951  # Washington, DC latitude
    default_lon = -77.0369  # Washington, DC longitude
    
    return {
        'region': os.environ.get('AWS_REGION', 'us-east-1'),
        'bias_latitude': float(os.environ.get('AWS_BIAS_LAT', default_lat)),
        'bias_longitude': float(os.environ.get('AWS_BIAS_LON', default_lon))
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


def _normalize_with_aws_suggest(address, places_client, bias_position=None):
    """
    Normalize an address using AWS Places API v2 Suggest endpoint.
    
    The Suggest API is more robust for handling malformed or duplicate addresses.
    It's designed for autocomplete scenarios and can handle partial or messy input.
    
    Args:
        address: The address string to normalize
        places_client: Boto3 geo-places client
        bias_position: Optional [latitude, longitude] to bias results toward a region
        
    Returns:
        Normalized address string or None if the service fails
    """
    if not address or not isinstance(address, str):
        return None
    
    try:
        # Build the suggest request with required parameters
        suggest_params = {
            'QueryText': address,
            'MaxResults': 1
        }
        
        # BiasPosition is required for the Suggest API
        if bias_position:
            suggest_params['BiasPosition'] = bias_position
        
        # Use the Suggest API for more robust address handling
        response = places_client.suggest(**suggest_params)
        
        # Check if we got results
        if not response.get('ResultItems'):
            return None
        
        # Get the first (best) result
        result = response['ResultItems'][0]
        
        # Use the Label field which includes full address with city/state/zip
        # This works for both POIs and regular addresses
        place_info = result.get('Place', {})
        address_obj = place_info.get('Address', {})
        address_text = address_obj.get('Label', '')
        
        if address_text:
            # Apply basic normalization to AWS result
            # Remove zip codes and country names like the local normalizer does
            normalized = normalize_address(address_text)
            return normalized
        
        return None
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        # Don't print error for common expected cases
        if error_code not in ['ResourceNotFoundException', 'AccessDeniedException']:
            print(f"AWS Places API Suggest error: {e}")
        return None
    except (NoCredentialsError, PartialCredentialsError):
        # Silently handle credential errors - these are logged at the higher level
        return None
    except Exception as e:
        print(f"Unexpected error in AWS Places API Suggest: {e}")
        return None


def _extract_place_name(original_address):
    """
    Extract a potential place/venue name from the original address string.
    
    Many event sources include venue names before the actual street address.
    If the address starts with something that's not a number or directional prefix,
    treat it as a potential place name.
    
    Args:
        original_address: The full location string potentially containing venue name
        
    Returns:
        Tuple of (place_name, remaining_address) or (None, original_address)
    """
    if not original_address or not isinstance(original_address, str):
        return None, original_address
    
    parts = [p.strip() for p in original_address.split(',')]
    
    if len(parts) <= 1:
        return None, original_address
    
    first_part = parts[0].strip()
    
    # Check if first part looks like a street address (starts with number or directional)
    if first_part and (first_part[0].isdigit() or 
                       first_part.startswith(('N ', 'S ', 'E ', 'W ', 
                                             'NE ', 'NW ', 'SE ', 'SW '))):
        # First part is already an address, no place name
        return None, original_address
    
    # First part doesn't look like a street address, treat it as potential place name
    # But avoid common noise like "Register to See Address"
    noise_phrases = {'register to see address'}
    if first_part.lower() in noise_phrases:
        return None, original_address
    
    return first_part, original_address


def _normalize_with_aws(address, places_client, bias_position=None):
    """
    Normalize an address using AWS Places API v2.
    
    This function tries two approaches:
    1. First tries search_text (standard search)
    2. If that fails, falls back to suggest (more robust for malformed input)
    
    Args:
        address: The address string to normalize
        places_client: Boto3 geo-places client
        bias_position: Optional [latitude, longitude] to bias results toward a region
        
    Returns:
        Normalized address string or None if the service fails
    """
    if not address or not isinstance(address, str):
        return None
    
    # Extract potential place name from original address
    place_name, _ = _extract_place_name(address)
    
    try:
        # Build the search_text request with required parameters
        search_params = {
            'QueryText': address,
            'MaxResults': 1
        }
        
        # BiasPosition is required for the Search API
        if bias_position:
            search_params['BiasPosition'] = bias_position
        
        # Try search_text first (standard approach)
        response = places_client.search_text(**search_params)
        
        # Check if we got results
        if response.get('ResultItems'):
            # Get the first (best) result
            result = response['ResultItems'][0]
            
            # Use the Label field which includes full address with city/state/zip
            # This works for both POIs and regular addresses
            address_obj = result.get('Address', {})
            address_text = address_obj.get('Label', '')
            
            if address_text:
                # Apply basic normalization to AWS result
                # Remove zip codes and country names like the local normalizer does
                normalized = normalize_address(address_text)
                return normalized
        
        # If search_text didn't return results, try suggest API
        # Suggest is more robust for handling malformed or duplicate addresses
        return _normalize_with_aws_suggest(address, places_client, bias_position)
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        # Don't print error for common expected cases
        if error_code not in ['ResourceNotFoundException', 'AccessDeniedException']:
            print(f"AWS Places API error: {e}")
        # Try suggest API as fallback
        return _normalize_with_aws_suggest(address, places_client, bias_position)
    except (NoCredentialsError, PartialCredentialsError):
        # Credentials are typically checked at client creation, but handle here for completeness
        # Try suggest API in case it can somehow work (though unlikely)
        return _normalize_with_aws_suggest(address, places_client, bias_position)
    except Exception as e:
        print(f"Unexpected error in AWS Places API: {e}")
        # Try suggest API as fallback
        return _normalize_with_aws_suggest(address, places_client, bias_position)
    
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
    bias_position = [aws_config['bias_latitude'], aws_config['bias_longitude']]
    
    # Try to use AWS Places API v2
    aws_result = None
    aws_available = False
    try:
        places_client = boto3.client('geo-places', region_name=aws_config['region'])
        aws_result = _normalize_with_aws(address, places_client, bias_position)
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
