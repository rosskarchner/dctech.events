#!/usr/bin/env python3
"""
Event classifier using AWS Bedrock Claude API
Classifies events with user-curated tags based on title, description, group, and website content
"""

import json
import yaml
import os
import hashlib
from datetime import datetime
import boto3

CACHE_DIR = '_cache'
TAGS_CACHE_FILE = os.path.join(CACHE_DIR, 'event_tags_cache.json')
TAGS_CONFIG_FILE = 'tags.yaml'

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)


def load_tags_config():
    """Load the tags configuration from tags.yaml"""
    if not os.path.exists(TAGS_CONFIG_FILE):
        return []
    
    with open(TAGS_CONFIG_FILE, 'r') as f:
        config = yaml.safe_load(f)
        return config.get('tags', [])


def get_tags_hash():
    """
    Calculate hash of current tags configuration
    Used to invalidate cache when tags change
    """
    tags = load_tags_config()
    tags_json = json.dumps(tags, sort_keys=True)
    return hashlib.md5(tags_json.encode()).hexdigest()


def load_tags_cache():
    """Load cached event classifications"""
    if os.path.exists(TAGS_CACHE_FILE):
        try:
            with open(TAGS_CACHE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading tags cache: {e}")
            return {'tags_hash': None, 'events': {}}
    return {'tags_hash': None, 'events': {}}


def save_tags_cache(cache):
    """Save event classifications to cache"""
    with open(TAGS_CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)


def get_event_cache_key(event):
    """
    Generate a cache key for an event based on immutable fields
    Uses title, group, and URL as unique identifier
    """
    key_parts = [
        event.get('title', ''),
        event.get('group', ''),
        event.get('url', '')
    ]
    key_str = '|'.join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()


def classify_event(event, tags):
    """
    Classify a single event using AWS Bedrock
    
    Args:
        event: Event dictionary with title, description, group, etc.
        tags: List of available tags from tags.yaml
    
    Returns:
        List of tag IDs that apply to this event
    """
    if not tags:
        return []
    
    # Build tag descriptions for the prompt
    tag_list = "\n".join([f"- {tag['id']}: {tag['description']}" for tag in tags])
    
    # Build event context
    event_text = f"""
Title: {event.get('title', '')}
Group: {event.get('group', '')}
Description: {event.get('description', '')}
URL: {event.get('url', '')}
"""
    
    prompt = f"""You are an event classifier. Classify the following event with ONLY the tags that clearly apply.

Available tags:
{tag_list}

Event to classify:
{event_text}

Return ONLY a JSON array of tag IDs that apply to this event, nothing else. Example: ["ai", "startups"]
If no tags apply, return an empty array: []

Your response:"""
    
    # Models to try in order (fastest/cheapest to most capable)
    models = [
        ('amazon.nova-lite-v1:0', 'nova'),
        ('amazon.nova-micro-v1:0', 'nova'),
        ('anthropic.claude-3-5-haiku-20241022-v1:0', 'claude')
    ]
    
    try:
        client = boto3.client('bedrock-runtime', region_name='us-east-1')
        
        for model_id, model_type in models:
            try:
                if model_type == 'nova':
                    # Nova uses the Converse API without 'type' field in content
                    response = client.converse(
                        modelId=model_id,
                        messages=[
                            {
                                'role': 'user',
                                'content': [
                                    {
                                        'text': prompt
                                    }
                                ]
                            }
                        ],
                        inferenceConfig={
                            'maxTokens': 200,
                            'temperature': 0.3
                        }
                    )
                    
                    # Extract the text response
                    if 'output' in response and 'message' in response['output']:
                        content = response['output']['message']['content']
                        if content and len(content) > 0:
                            text = content[0]['text'].strip()
                            
                            # Remove markdown code blocks if present
                            if text.startswith('```'):
                                # Extract JSON from markdown code blocks
                                lines = text.split('\n')
                                json_lines = []
                                in_block = False
                                for line in lines:
                                    if line.startswith('```'):
                                        in_block = not in_block
                                    elif in_block:
                                        json_lines.append(line)
                                text = '\n'.join(json_lines)
                            
                            # Try to parse the JSON array
                            try:
                                tags_result = json.loads(text)
                                if isinstance(tags_result, list):
                                    # Filter to only valid tag IDs
                                    valid_tag_ids = {tag['id'] for tag in tags}
                                    return [t for t in tags_result if t in valid_tag_ids]
                            except json.JSONDecodeError:
                                print(f"Failed to parse response as JSON from {model_id}: {text}")
                                continue
                else:
                    # Claude uses invoke_model with the Messages API format
                    response = client.invoke_model(
                        modelId=model_id,
                        body=json.dumps({
                            'anthropic_version': 'bedrock-2023-06-01',
                            'max_tokens': 200,
                            'messages': [
                                {
                                    'role': 'user',
                                    'content': prompt
                                }
                            ]
                        })
                    )
                    
                    response_body = json.loads(response['body'].read())
                    
                    # Extract the text response
                    if 'content' in response_body and len(response_body['content']) > 0:
                        text = response_body['content'][0]['text'].strip()
                        
                        # Try to parse the JSON array
                        try:
                            tags_result = json.loads(text)
                            if isinstance(tags_result, list):
                                # Filter to only valid tag IDs
                                valid_tag_ids = {tag['id'] for tag in tags}
                                return [t for t in tags_result if t in valid_tag_ids]
                        except json.JSONDecodeError:
                            print(f"Failed to parse response as JSON from {model_id}: {text}")
                            continue
                
                # If we got here, the response was parsed successfully
                return []
                
            except Exception as model_error:
                # Try next model
                print(f"Model {model_id} failed: {model_error}")
                continue
        
        # All models failed
        print(f"All classification models failed")
        return []
    
    except Exception as e:
        print(f"Error calling AWS Bedrock: {e}")
        return []


def classify_events(events, skip_cache=False):
    """
    Classify a list of events, using cache when possible
    
    Args:
        events: List of event dictionaries
        skip_cache: If True, re-classify all events even if cached
    
    Returns:
        List of events with 'tags' field added
    """
    tags = load_tags_config()
    
    if not tags:
        print("Warning: No tags configured in tags.yaml")
        return events
    
    # Load cache and check if tags config has changed
    cache = load_tags_cache()
    current_tags_hash = get_tags_hash()
    tags_changed = cache.get('tags_hash') != current_tags_hash
    
    if tags_changed:
        print("Tags configuration changed, re-classifying all events")
        cache = {'tags_hash': current_tags_hash, 'events': {}}
        skip_cache = True
    
    # Classify events
    classified_events = []
    newly_classified = 0
    
    for event in events:
        cache_key = get_event_cache_key(event)
        
        if not skip_cache and cache_key in cache['events']:
            # Use cached classification
            event['tags'] = cache['events'][cache_key]
        else:
            # Classify the event
            event['tags'] = classify_event(event, tags)
            cache['events'][cache_key] = event['tags']
            newly_classified += 1
        
        classified_events.append(event)
    
    # Save cache
    cache['tags_hash'] = current_tags_hash
    save_tags_cache(cache)
    
    print(f"Classification complete: {newly_classified} new classifications, {len(events) - newly_classified} from cache")
    
    return classified_events
