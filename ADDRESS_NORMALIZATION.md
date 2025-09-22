# Address Normalization

This project includes automatic address normalization to clean up redundant information commonly found in event addresses from various sources (especially Meetup).

## What it fixes

The normalization function removes common redundancies like:

- **Consecutive duplicates**: `14140 Parke Long Ct, 14140 Parke Long Ct, Chantilly, VA, Chantilly, VA` → `14140 Parke Long Ct, Chantilly, VA`
- **State abbreviation duplicates**: `Arlington, VA, Arlington, VA` → `Arlington, VA`
- **Mixed case duplicates**: `ARLINGTON, VA, Arlington, VA` → `Arlington, VA`
- **Embedded state duplicates**: `Washington, DC, DC` → `Washington, DC`

## Implementation

The normalization is implemented in `address_utils.py` and automatically applied to:

- iCal event locations (in `generate_month_data.py`)
- RSS event locations (in `refresh_calendars.py`)
- Single event locations (in `generate_month_data.py`)

## Usage

The normalization happens automatically during data processing. No manual intervention is required.

```python
from address_utils import normalize_address

# Example usage
original = "Vernon Smith Hall, 3434 Washington Blvd, Arlington, VA 22201, ARLINGTON, VA, ARLINGTON, VA"
normalized = normalize_address(original)
# Result: "Vernon Smith Hall, 3434 Washington Blvd, Arlington, VA 22201"
```

## Algorithm

1. Split address by commas and trim whitespace
2. Remove consecutive duplicates (case-insensitive)
3. Remove repeating city/state patterns at the end
4. Remove non-consecutive duplicates
5. Handle common state abbreviation duplicates