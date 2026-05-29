from calgen.location_utils import extract_location_info
from calgen.regions import EventRejected

_REGIONS = [
    {'slug': 'dc', 'name': 'Washington DC'},
    {'slug': 'md', 'name': 'Maryland'},
    {'slug': 'va', 'name': 'Virginia'},
]

_STATE_TO_SLUG = {
    'DC': 'dc',
    'MD': 'md',
    'VA': 'va',
}

# US state codes that are clearly not in the DC metro area.
# Events with these states are rejected outright.
_EXCLUDED_STATES = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'WA', 'WV', 'WI', 'WY',
    'PR', 'VI', 'GU', 'MP', 'AS',
}


def list_regions():
    return _REGIONS


def location_to_region(location_str):
    _, state = extract_location_info(location_str or '')
    if not state:
        return None
    state_upper = state.upper()
    if state_upper in _EXCLUDED_STATES:
        raise EventRejected(f"Event is in {state_upper}, outside DC metro area")
    return _STATE_TO_SLUG.get(state_upper)
