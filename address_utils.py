#!/usr/bin/env python3
import re

def normalize_address(address):
    """
    Normalize addresses by removing redundant information.
    
    Args:
        address: The address string to normalize
        
    Returns:
        Normalized address string
    """
    if not address or not isinstance(address, str):
        return address
    
    # Split by commas and clean each part
    parts = [part.strip() for part in address.split(',')]
    
    # Remove empty parts
    parts = [part for part in parts if part]
    
    if len(parts) <= 1:
        return address
    
    # Remove consecutive duplicates (case-insensitive)
    normalized_parts = []
    for part in parts:
        if not normalized_parts or part.lower() != normalized_parts[-1].lower():
            normalized_parts.append(part)
    
    # Remove state/city duplicates at the end
    # Common pattern: "City, State, City, State" -> "City, State"
    if len(normalized_parts) >= 4:
        # Check if last two parts repeat the previous two (case-insensitive)
        if (normalized_parts[-1].lower() == normalized_parts[-3].lower() and 
            normalized_parts[-2].lower() == normalized_parts[-4].lower()):
            normalized_parts = normalized_parts[:-2]
    
    # Remove exact duplicates that aren't consecutive (case-insensitive)
    seen = set()
    final_parts = []
    for part in normalized_parts:
        part_lower = part.lower()
        if part_lower not in seen:
            seen.add(part_lower)
            final_parts.append(part)
    
    # Handle common state abbreviation duplicates (e.g., "Arlington, VA, VA")
    if len(final_parts) >= 2:
        # Check if last part is a state abbreviation that's already in the second-to-last part
        last_part = final_parts[-1].strip()
        second_last = final_parts[-2].strip()
        
        # Common state abbreviations
        states = {'VA', 'DC', 'MD', 'WV'}
        
        if (last_part in states and 
            (last_part in second_last or second_last.endswith(f' {last_part}'))):
            final_parts = final_parts[:-1]
    
    return ', '.join(final_parts)