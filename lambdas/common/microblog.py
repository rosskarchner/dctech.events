import requests

def get_micropub_destination(token, target_url='https://updates.dctech.events'):
    """
    Fetch Micro.blog config and find the UID for the target blog URL.
    Returns the UID if found, otherwise returns the target_url as fallback.
    """
    try:
        print(f"Fetching Micro.blog config to find destination for {target_url}...")
        resp = requests.get(
            'https://micro.blog/micropub?q=config',
            headers={'Authorization': f'Bearer {token}'},
            timeout=10
        )
        resp.raise_for_status()
        config = resp.json()
        
        destinations = config.get('destination', [])
        if not destinations:
            print("No destinations found in Micro.blog config.")
            return target_url
            
        for dest in destinations:
            # Check if the URL matches (Micro.blog might return with or without trailing slash)
            dest_url = dest.get('url', '').rstrip('/')
            clean_target = target_url.rstrip('/')
            
            if dest_url == clean_target:
                uid = dest.get('uid')
                if uid:
                    print(f"Found destination UID: {uid} for {target_url}")
                    return uid
        
        print(f"Could not find destination UID for {target_url} in config.")
        return target_url
        
    except Exception as e:
        print(f"Error fetching Micro.blog config: {e}")
        return target_url
