#!/usr/bin/env python3
import re

def extract_location_info(address):
    """Extract city and state from an address string."""
    if not address:
        return None, None

    # Pattern to match: [anything], City, State [ZIP] [, USA]
    # Updated to accept any two-letter state code, not just DC/VA/MD
    pattern = r'([^,]+),\s*([^,]+),\s*([A-Z]{2})(?:\s+\d{5})?(?:,\s*USA)?$'
    match = re.search(pattern, address, re.IGNORECASE)

    if match:
        _, city, state = match.groups()
        city = city.strip()
        state = state.upper()

        # Skip if "city" looks like a street address or building
        if (re.search(r'\d+\s+\w+\s+(st|street|ave|avenue|blvd|boulevard|dr|drive|rd|road|ct|court|ln|lane|way|pl|place)', city, re.IGNORECASE) or
            re.search(r'suite|floor|#|room|building', city, re.IGNORECASE) or
            len(city.split()) > 4):  # Very long "city" names are likely addresses
            return None, None

        # Handle special cases
        if state == 'DC':
            city = 'Washington'

        return city, state

    return None, None

def get_region_name(state):
    """Get region name from state abbreviation."""
    regions = {
        'DC': 'Washington DC',
        'VA': 'Virginia',
        'MD': 'Maryland'
    }
    return regions.get(state, state)