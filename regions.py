from calgen.location_utils import extract_location_info

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


def list_regions():
    return _REGIONS


def location_to_region(location_str):
    _, state = extract_location_info(location_str or '')
    return _STATE_TO_SLUG.get((state or '').upper())
