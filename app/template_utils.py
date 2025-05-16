import json
import re
import html

def sanitize_text(text):
    """
    Simple function to handle None values and convert to string.
    No sanitization is performed as requested.
    
    Args:
        text: The text to handle
        
    Returns:
        String representation of the input
    """
    if text is None:
        return ""
    
    # Convert to string if not already
    if not isinstance(text, str):
        text = str(text)
    
    return text

def prepare_group_for_template(group):
    """
    Prepares a group object for use in templates by ensuring all text fields
    are properly sanitized and formatted.
    
    Args:
        group: The group object from DynamoDB
        
    Returns:
        A sanitized and prepared group object for template rendering
    """
    if not group:
        return {}
    
    # Create a copy to avoid modifying the original
    prepared = dict(group)
    
    # Sanitize text fields
    for key in ['name', 'website', 'ical', 'fallback_url', 'organization_name']:
        if key in prepared:
            prepared[key] = sanitize_text(prepared[key])
    
    # Ensure HTML-safe content
    for key in ['name', 'organization_name']:
        if key in prepared:
            prepared[key] = html.escape(prepared[key])
    
    return prepared

def prepare_event_for_template(event):
    """
    Prepares an event object for use in templates by ensuring all text fields
    are properly sanitized and formatted.
    
    Args:
        event: The event object from DynamoDB
        
    Returns:
        A sanitized and prepared event object for template rendering
    """
    if not event:
        return {}
    
    # Create a copy to avoid modifying the original
    prepared = dict(event)
    
    # Sanitize text fields
    for key in ['title', 'description', 'location', 'url', 'groupName', 'groupWebsite']:
        if key in prepared:
            prepared[key] = sanitize_text(prepared[key])
    
    # Ensure HTML-safe content for display fields
    for key in ['title', 'groupName']:
        if key in prepared:
            prepared[key] = html.escape(prepared[key])
    
    return prepared