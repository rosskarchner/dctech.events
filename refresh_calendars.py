#!/usr/bin/env python3
"""Thin wrapper — delegates to calgen.calendars for backward compatibility."""
from calgen.calendars import *  # noqa: F401,F403
from calgen.calendars import main

if __name__ == "__main__":
    import sys
    sys.exit(main())
