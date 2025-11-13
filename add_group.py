#!/usr/bin/env python3
"""
Script to fetch Meetup group info and create YAML entries in the _groups directory.
"""

import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: This script requires 'requests' and 'beautifulsoup4'")
    print("Install them with: pip install requests beautifulsoup4")
    sys.exit(1)


def extract_group_name(url):
    """Fetch the Meetup page and extract the group name."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Try to find the group name in the title or h1
        title = soup.find('title')
        if title:
            # Format is usually "GroupName | Meetup"
            text = title.get_text()
            group_name = text.split('|')[0].strip()
            if group_name:
                return group_name

        # Try h1 tag as fallback
        h1 = soup.find('h1')
        if h1:
            return h1.get_text().strip()

        return None
    except requests.RequestException as e:
        print(f"Error fetching URL: {e}")
        return None


def extract_group_id(url):
    """Extract the group ID from the Meetup URL."""
    parsed = urlparse(url)
    path = parsed.path.strip('/')
    # Remove trailing slash if present
    return path.rstrip('/')


def create_yaml_entry(url, group_name, city='dc'):
    """Create a YAML file entry for the group."""
    group_id = extract_group_id(url)

    # Sanitize filename
    filename = group_id.replace('/', '-') + '.yaml'
    filepath = Path('cities') / city / '_groups' / filename

    # Check if file already exists
    if filepath.exists():
        response = input(f"File {filename} already exists. Overwrite? (y/n): ").strip().lower()
        if response != 'y':
            print("Skipped.")
            return False

    yaml_content = f"""name: {group_name}
website: {url}
rss: {url}events/rss/
active: true
"""

    try:
        filepath.write_text(yaml_content)
        print(f"✓ Created {filename}")
        return True
    except Exception as e:
        print(f"Error writing file: {e}")
        return False


def main():
    """Main loop for adding groups."""
    os.chdir(Path(__file__).parent)

    # Get city from command line or prompt
    city = 'dc'  # default
    if len(sys.argv) > 1:
        city = sys.argv[1]
    else:
        city_input = input("Enter city (default: dc): ").strip().lower()
        if city_input:
            city = city_input

    # Check if city directory exists
    city_path = Path('cities') / city / '_groups'
    if not city_path.exists():
        print(f"Error: City directory '{city}' does not exist")
        print("Available cities:")
        for city_dir in Path('cities').iterdir():
            if city_dir.is_dir():
                print(f"  - {city_dir.name}")
        return

    print(f"Meetup Group Adder - {city.upper()}")
    print("=" * 50)
    print("Enter Meetup URLs one at a time.")
    print("(Type 'quit' or 'exit' to stop)\n")

    while True:
        try:
            url = input("Enter Meetup URL: ").strip()

            if url.lower() in ('quit', 'exit', 'q'):
                print("Goodbye!")
                break

            if not url:
                print("Please enter a URL.")
                continue

            # Ensure URL ends with /
            if not url.endswith('/'):
                url += '/'

            # Validate it's a meetup URL
            if 'meetup.com' not in url:
                print("Error: URL must be from meetup.com")
                continue

            print(f"\nFetching: {url}")
            group_name = extract_group_name(url)

            if not group_name:
                print("Error: Could not extract group name from URL")
                continue

            print(f"Group name: {group_name}")
            create_yaml_entry(url, group_name, city)
            print()

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            continue


if __name__ == '__main__':
    main()
