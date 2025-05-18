#!/usr/bin/env python3
"""
Simple verification script to check if the route conflict has been resolved.
"""

import sys

def test_flask_app():
    """Test that the Flask app can be imported and initialized without route conflicts."""
    try:
        # Add the current directory to the path
        sys.path.append('.')
        
        # Import the Flask app
        from app.app import app
        
        # Import the route modules
        from app.events_routes import register_events_routes
        from app.groups_routes import register_groups_routes
        
        print("✅ Flask app and route modules import successful")
        
        # Create a test Flask app
        from flask import Flask
        test_app = Flask(__name__)
        
        # Register the routes
        register_events_routes(test_app, None, None)
        register_groups_routes(test_app, None)
        
        print("✅ Routes registered successfully without conflicts")
        
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    print("Running verification test...")
    success = test_flask_app()
    
    if success:
        print("\n✅ Verification test passed! The route conflict has been resolved.")
        sys.exit(0)
    else:
        print("\n❌ Verification test failed! The route conflict still exists.")
        sys.exit(1)