#!/usr/bin/env python3
"""
Track events - DEPRECATED.
Tracking is now handled by DynamoDB sync in generate_month_data.py / db_utils.py.
This script is kept as a no-op to prevent CI/CD failures until workflows are updated.
"""
import sys

def main():
    print("Event tracking is now handled by DynamoDB sync.")
    return 0

if __name__ == "__main__":
    sys.exit(main())