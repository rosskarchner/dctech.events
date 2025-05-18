#!/usr/bin/env python3
import sys
sys.path.append('.')
try:
    from app.app import app
    from app.events_routes import register_events_routes
    from app.groups_routes import register_groups_routes
    print("✅ Flask app and route modules import successful")
except Exception as e:
    print(f"❌ Flask app import failed: {e}")
    sys.exit(1)