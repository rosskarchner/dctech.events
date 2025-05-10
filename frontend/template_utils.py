import json
import re
import html

def sanitize_text(text):
    """
    Ensure text is properly encoded as UTF-8 and handle any encoding issues.
    
    Args:
        text: The text to sanitize
        
    Returns:
        Sanitized text as UTF-8 string
    """
    if text is None:
        return ""
    
    # Convert to string if not already
    if not isinstance(text, str):
        text = str(text)
    
    try:
        # Try to encode and then decode to ensure proper UTF-8
        return text.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        # If any error occurs, return a safe string
        return "[Text encoding error]"

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