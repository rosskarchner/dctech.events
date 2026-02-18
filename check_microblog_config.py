#!/usr/bin/env python3
"""
Validate micro.blog configuration.

This script checks that the MICROBLOG_DESTINATION environment variable
is set to the correct value for dctech.events posts.

Usage:
    export MICROBLOG_DESTINATION="https://updates.dctech.events"
    python check_microblog_config.py
"""

import os
import sys

# Expected configuration
EXPECTED_DESTINATION = "https://updates.dctech.events"
INCORRECT_DESTINATIONS = [
    "https://ross.karchner.com/",
    "https://ross.karchner.com",
    "https://updates.dctech.events/",  # Trailing slash is incorrect
]


def check_microblog_destination():
    """
    Verify that MICROBLOG_DESTINATION is correctly configured.
    
    Since the default is now set in the code, this checks if the environment
    variable is set to a wrong value. If not set, it will use the correct default.
    
    Returns:
        int: 0 if valid, 1 if invalid
    """
    destination = os.environ.get('MICROBLOG_DESTINATION')
    
    if not destination:
        print("ℹ️  MICROBLOG_DESTINATION environment variable is not set")
        print(f"   Will use default: {EXPECTED_DESTINATION}")
        print("   (This is correct - the default is now set in the code)")
        return 0
    
    if destination in INCORRECT_DESTINATIONS:
        print(f"❌ MICROBLOG_DESTINATION is set to wrong blog: {destination}")
        print(f"   Expected: {EXPECTED_DESTINATION}")
        print(f"   Found:    {destination}")
        print("\nThis will cause posts to go to the wrong micro.blog blog!")
        print("\nTo fix, either:")
        print(f'   1. export MICROBLOG_DESTINATION="{EXPECTED_DESTINATION}"')
        print("   2. Unset the variable to use the default:")
        print("      unset MICROBLOG_DESTINATION")
        print("\nFor GitHub Actions, update or remove the repository variable:")
        print("   Settings → Secrets and variables → Actions → Repository variables")
        return 1
    
    if destination != EXPECTED_DESTINATION:
        print(f"⚠️  MICROBLOG_DESTINATION is set to unexpected value: {destination}")
        print(f"   Expected: {EXPECTED_DESTINATION}")
        print(f"   Found:    {destination}")
        print("\nThis may be intentional for testing, but production should use:")
        print(f"   {EXPECTED_DESTINATION}")
        return 1
    
    print(f"✅ MICROBLOG_DESTINATION is correctly configured")
    print(f"   Destination: {destination}")
    return 0


def check_mb_token():
    """
    Verify that MB_TOKEN is set (don't print the actual value).
    
    Returns:
        int: 0 if set, 1 if missing
    """
    token = os.environ.get('MB_TOKEN')
    
    if not token:
        print("❌ MB_TOKEN environment variable is not set")
        print("   This is required for posting to micro.blog")
        print("\nTo fix:")
        print('   export MB_TOKEN="your-app-token-here"')
        print("\nGet your token from: https://micro.blog/account/apps")
        return 1
    
    # Basic validation - token should be reasonably long
    if len(token) < 20:
        print("⚠️  MB_TOKEN seems too short, may be invalid")
        return 1
    
    print("✅ MB_TOKEN is set")
    return 0


def main():
    """Main function to run all configuration checks."""
    print("Checking micro.blog configuration...\n")
    
    destination_status = check_microblog_destination()
    print()
    token_status = check_mb_token()
    
    print("\n" + "=" * 60)
    
    if destination_status == 0 and token_status == 0:
        print("✅ All micro.blog configuration checks passed!")
        print("\nYou can now post to micro.blog:")
        print("   python post_newsletter_to_microblog.py --dry-run")
        print("   python post_daily_event_summary.py --dry-run")
        print("   python post_todays_events_to_microblog.py --dry-run")
        return 0
    else:
        print("❌ Some configuration checks failed")
        print("\nPlease fix the issues above before posting to micro.blog")
        print("\nSee MICROBLOG_CONFIGURATION.md for detailed documentation")
        return 1


if __name__ == "__main__":
    sys.exit(main())
