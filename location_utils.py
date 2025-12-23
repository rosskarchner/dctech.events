#!/usr/bin/env python3
import usaddress

def extract_location_info(address):
    """
    Extract city and state from an address string.
    
    Uses usaddress library to parse addresses and extract PlaceName and StateName.
    Handles multi-word cities by collecting consecutive PlaceNames immediately before StateName.
    
    Args:
        address: Address string in various formats (street address, city/state, etc.)
        
    Returns:
        Tuple of (city, state) or (None, None) if extraction fails
    """
    if not address or not isinstance(address, str):
        return None, None

    try:
        parsed = usaddress.parse(address)
        state = None
        state_index = None
        city_parts = []
        
        # Find state and collect consecutive PlaceNames immediately before it
        for i, (value, component_type) in enumerate(parsed):
            if component_type == 'StateName':
                state = value.rstrip(',').strip().upper()
                state_index = i
                break
        
        if state is None or state_index is None:
            return None, None
        
        # Collect PlaceNames immediately before the state (working backwards)
        for i in range(state_index - 1, -1, -1):
            value, component_type = parsed[i]
            if component_type == 'PlaceName':
                city_parts.insert(0, value.rstrip(',').strip())
            else:
                # Stop at first non-PlaceName
                break
        
        if not city_parts:
            return None, None
        
        city = ' '.join(city_parts)
        
        # Map full state names to abbreviations
        state_map = {
            'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR',
            'CALIFORNIA': 'CA', 'COLORADO': 'CO', 'CONNECTICUT': 'CT', 'DELAWARE': 'DE',
            'FLORIDA': 'FL', 'GEORGIA': 'GA', 'HAWAII': 'HI', 'IDAHO': 'ID',
            'ILLINOIS': 'IL', 'INDIANA': 'IN', 'IOWA': 'IA', 'KANSAS': 'KS',
            'KENTUCKY': 'KY', 'LOUISIANA': 'LA', 'MAINE': 'ME', 'MARYLAND': 'MD',
            'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI', 'MINNESOTA': 'MN', 'MISSISSIPPI': 'MS',
            'MISSOURI': 'MO', 'MONTANA': 'MT', 'NEBRASKA': 'NE', 'NEVADA': 'NV',
            'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ', 'NEW MEXICO': 'NM', 'NEW YORK': 'NY',
            'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND', 'OHIO': 'OH', 'OKLAHOMA': 'OK',
            'OREGON': 'OR', 'PENNSYLVANIA': 'PA', 'RHODE ISLAND': 'RI', 'SOUTH CAROLINA': 'SC',
            'SOUTH DAKOTA': 'SD', 'TENNESSEE': 'TN', 'TEXAS': 'TX', 'UTAH': 'UT',
            'VERMONT': 'VT', 'VIRGINIA': 'VA', 'WASHINGTON': 'WA', 'WEST VIRGINIA': 'WV',
            'WISCONSIN': 'WI', 'WYOMING': 'WY', 'DISTRICT OF COLUMBIA': 'DC'
        }
        
        # If state is a full name, convert to abbreviation
        if state in state_map:
            state = state_map[state]
        
        # Handle special case: DC should be mapped to Washington
        if state == 'DC':
            city = 'Washington'
        
        return city, state
        
    except (usaddress.RepeatedLabelError, ValueError):
        # If usaddress can't parse it, return None
        return None, None
    except Exception:
        return None, None

def get_region_name(state):
    """Get region name from state abbreviation."""
    regions = {
        'DC': 'Washington DC',
        'VA': 'Virginia',
        'MD': 'Maryland'
    }
    return regions.get(state, state)