#!/usr/bin/env python3
"""Thin wrapper — delegates to calgen.pipeline for backward compatibility."""
from calgen.pipeline import *  # noqa: F401,F403
from calgen.event_utils import calculate_event_hash  # noqa: F401
from calgen.pipeline import main

# Backward-compatibility aliases
load_event_overrides = load_overlays  # noqa: F405
EVENT_OVERRIDES_DIR = OVERLAY_DIR  # noqa: F405

if __name__ == "__main__":
    import sys
    sys.exit(main())
