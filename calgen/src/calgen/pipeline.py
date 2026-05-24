#!/usr/bin/env python3
"""
Data pipeline: reads groups, iCal caches, single events, and recurring events,
then writes _data/all_events.json.
"""
import os
import yaml
import icalendar
import pytz
from datetime import datetime, timedelta, timezone, date
import re
from pathlib import Path
import sys
import calendar as cal_module
import dateparser
import json
import requests
from dateutil import rrule

from calgen.location_utils import extract_location_info
from calgen.site_config import get_config
from calgen.event_utils import calculate_event_hash

config = get_config()
timezone_name = config.get('timezone', 'US/Eastern')
local_tz = pytz.timezone(timezone_name)
ALLOWED_STATES = config.get('only_states', [])

DATA_DIR = '_data'
CACHE_DIR = '_cache'
ICAL_CACHE_DIR = os.path.join(CACHE_DIR, 'ical')
GROUPS_DIR = '_groups'
CATEGORIES_DIR = '_categories'
SINGLE_EVENTS_DIR = '_single_events'
OVERLAY_DIR = '_overlay'
RECURRING_EVENTS_DIR = '_recurring_events'

_OVERLAY_PROTECTED_FIELDS = {'group', 'group_id', 'group_website', 'date', 'end_date', 'guid', 'source'}

VALID_US_STATES = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
    'DC', 'PR', 'VI', 'GU', 'MP', 'AS',
}

DC_TYPO_CODES = {'DI', 'CD'}
ICAL_MAX_FUTURE_DAYS = 90
RECURRING_MAX_FUTURE_DAYS = 90


def is_event_in_allowed_states(event, allowed_states):
    if not allowed_states:
        return True
    location = event.get('location') or ''
    if not location:
        return True

    city, state = extract_location_info(location)
    if state is not None:
        state_upper = state.upper()
        if state_upper in VALID_US_STATES:
            return state_upper in allowed_states
        if 'DC' in allowed_states:
            city_upper = (city or '').upper()
            if city_upper == 'WASHINGTON' or state_upper in DC_TYPO_CODES:
                return True
        return False

    found_states = set()
    for state_code in VALID_US_STATES:
        if re.search(r'\b' + re.escape(state_code) + r'\b', location, re.IGNORECASE):
            found_states.add(state_code.upper())

    if found_states:
        return bool(found_states & set(allowed_states))
    return True


def are_events_duplicates(e1, e2):
    return (e1.get('title') == e2.get('title') and
            e1.get('date') == e2.get('date') and
            e1.get('time') == e2.get('time'))


def remove_duplicates(events):
    guid_index = {}
    for i, e in enumerate(events):
        if e.get('guid'):
            guid_index[e['guid']] = i

    result = []
    seen_indices = set()
    explicit_children = set()

    for i, event in enumerate(events):
        dup_of = event.get('duplicate_of')
        if dup_of and dup_of in guid_index:
            parent = events[guid_index[dup_of]]
            parent.setdefault('also_published_by', []).append({
                'group': event.get('group'),
                'group_website': event.get('group_website'),
            })
            explicit_children.add(i)

    for i, event in enumerate(events):
        if i in explicit_children or i in seen_indices:
            continue
        duplicate_found = False
        for j in range(len(result)):
            if are_events_duplicates(result[j], event):
                result[j].setdefault('also_published_by', []).append({
                    'group': event.get('group'),
                    'group_website': event.get('group_website'),
                })
                duplicate_found = True
                break
        if not duplicate_found:
            result.append(event)
        seen_indices.add(i)
    return result


def get_groups():
    groups = []
    if not os.path.exists(GROUPS_DIR):
        return groups
    for filename in os.listdir(GROUPS_DIR):
        if filename.endswith('.yaml'):
            slug = filename[:-5]
            with open(os.path.join(GROUPS_DIR, filename), 'r') as f:
                group = yaml.safe_load(f)
                group['id'] = slug
                groups.append(group)
    return groups


def get_categories():
    categories = {}
    if not os.path.exists(CATEGORIES_DIR):
        return categories
    for filename in os.listdir(CATEGORIES_DIR):
        if filename.endswith('.yaml'):
            slug = filename[:-5]
            with open(os.path.join(CATEGORIES_DIR, filename), 'r') as f:
                categories[slug] = yaml.safe_load(f)
                categories[slug]['slug'] = slug
    return categories


def load_single_events():
    events = []
    if not os.path.exists(SINGLE_EVENTS_DIR):
        return events
    for filename in os.listdir(SINGLE_EVENTS_DIR):
        if not filename.endswith('.yaml'):
            continue
        filepath = os.path.join(SINGLE_EVENTS_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                event = yaml.safe_load(f)
            if not event:
                continue
            event['id'] = os.path.splitext(filename)[0]
            event['source'] = 'manual'
            if 'date' in event:
                if isinstance(event['date'], date):
                    event['date'] = event['date'].strftime('%Y-%m-%d')
                else:
                    parsed = dateparser.parse(str(event['date']), settings={
                        'TIMEZONE': timezone_name,
                        'DATE_ORDER': 'YMD',
                        'PREFER_DATES_FROM': 'future',
                    })
                    if parsed:
                        event['date'] = parsed.strftime('%Y-%m-%d')
            event['guid'] = calculate_event_hash(
                event.get('date', ''),
                event.get('time', ''),
                event.get('title', ''),
                event.get('url'),
            )
            events.append(event)
        except Exception as e:
            print(f"Error loading single event {filename}: {e}")
    return events


def load_overlays():
    overlays = {}
    if not os.path.exists(OVERLAY_DIR):
        return overlays
    for filename in os.listdir(OVERLAY_DIR):
        if not filename.endswith('.yaml'):
            continue
        guid = os.path.splitext(filename)[0]
        filepath = os.path.join(OVERLAY_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            if data:
                overlays[guid] = data
        except Exception as e:
            print(f"Error loading overlay {filepath}: {e}")
    return overlays


def load_recurring_events():
    events = []
    if not os.path.exists(RECURRING_EVENTS_DIR):
        return events
    for filename in os.listdir(RECURRING_EVENTS_DIR):
        if not filename.endswith('.yaml'):
            continue
        filepath = os.path.join(RECURRING_EVENTS_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                event = yaml.safe_load(f)
            if not event:
                continue
            event['id'] = os.path.splitext(filename)[0]
            event['source'] = 'recurring'
            event['is_recurring'] = True
            if 'date' in event:
                if isinstance(event['date'], date):
                    event['date'] = event['date'].strftime('%Y-%m-%d')
                else:
                    parsed = dateparser.parse(str(event['date']), settings={
                        'TIMEZONE': timezone_name,
                        'DATE_ORDER': 'YMD',
                        'PREFER_DATES_FROM': 'future',
                    })
                    if parsed:
                        event['date'] = parsed.strftime('%Y-%m-%d')
            events.append(event)
        except Exception as e:
            print(f"Error loading recurring event {filename}: {e}")
    return events


def expand_recurring_events(recurring_events, today=None, max_days=RECURRING_MAX_FUTURE_DAYS):
    if today is None:
        today = datetime.now(local_tz).date()
    expanded = []
    max_date = today + timedelta(days=max_days)
    for event in recurring_events:
        rrule_str = event.get('rrule', '')
        if not rrule_str:
            continue
        try:
            start_date = datetime.strptime(event['date'], '%Y-%m-%d').date()
        except (KeyError, ValueError):
            continue
        if start_date > max_date:
            continue
        try:
            start_dt = local_tz.localize(datetime.combine(start_date, datetime.min.time()))
            rule = rrule.rrulestr(rrule_str, dtstart=start_dt)
            for occurrence_dt in rule:
                occurrence_date = occurrence_dt.date()
                if occurrence_date > max_date:
                    break
                if occurrence_date < today:
                    continue
                instance = dict(event)
                instance['date'] = occurrence_date.strftime('%Y-%m-%d')
                instance['guid'] = calculate_event_hash(
                    instance['date'],
                    instance.get('time', ''),
                    instance['title'],
                    instance.get('url'),
                )
                expanded.append(instance)
        except Exception as e:
            print(f"Error expanding recurring event {event.get('id', 'unknown')}: {e}")
    return expanded


def process_events(groups, categories, single_events, ical_events, recurring_events,
                   allowed_states, today=None, event_overrides=None):
    if today is None:
        today = datetime.now(local_tz).date()
    if event_overrides is None:
        event_overrides = {}

    max_ical_date = today + timedelta(days=ICAL_MAX_FUTURE_DAYS)
    regular_events = []
    submitted_events = []

    for group in groups:
        if not group.get('active', True):
            continue
        group_id = group.get('id', '')
        suppress_urls = group.get('suppress_urls') or []
        if suppress_urls is True or suppress_urls is False:
            suppress_urls = []
        for event in ical_events.get(group_id, []):
            if event.get('url', '') in suppress_urls:
                continue
            try:
                event_date = datetime.strptime(event['date'], '%Y-%m-%d').date()
            except (KeyError, ValueError):
                continue
            if event_date < today or event_date > max_ical_date:
                continue
            if not is_event_in_allowed_states(event, allowed_states):
                continue
            processed = dict(event)
            processed['group'] = group.get('name', group_id)
            processed['group_website'] = group.get('website', '')
            processed['source'] = 'ical'
            processed['categories'] = list(group.get('categories', []))
            processed['guid'] = calculate_event_hash(
                event.get('date', ''), event.get('time', ''),
                event.get('title', ''), event.get('url'),
            )
            override = event_overrides.get(processed['guid'])
            if override:
                for key, value in override.items():
                    if key not in _OVERLAY_PROTECTED_FIELDS:
                        processed[key] = value
            regular_events.append(processed)

    for event in single_events:
        try:
            event_date = datetime.strptime(event['date'], '%Y-%m-%d').date()
        except (KeyError, ValueError):
            continue
        if event_date < today:
            continue
        if not is_event_in_allowed_states(event, allowed_states):
            continue
        processed = dict(event)
        processed.setdefault('source', 'manual')
        if 'guid' not in processed:
            processed['guid'] = calculate_event_hash(
                event.get('date', ''), event.get('time', ''),
                event.get('title', ''), event.get('url'),
            )
        submitted_events.append(processed)

    recurring_expanded = expand_recurring_events(recurring_events, today=today)
    combined = regular_events + recurring_expanded + submitted_events
    unique_events = remove_duplicates(combined)

    def _sort_time(event):
        t = event.get('time', '')
        if isinstance(t, dict):
            return t.get(event.get('date', ''), '') or ''
        return t or ''

    unique_events.sort(key=lambda x: (x.get('date', ''), _sort_time(x)))
    return unique_events


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    groups = get_groups()
    categories = get_categories()
    single_events = load_single_events()
    recurring_events = load_recurring_events()
    event_overrides = load_overlays()

    ical_events = {}
    for group in groups:
        group_id = group['id']
        cache_file = os.path.join(ICAL_CACHE_DIR, f"{group_id}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    ical_events[group_id] = json.load(f)
            except Exception as e:
                print(f"Error reading cache {cache_file}: {e}")

    unique_events = process_events(
        groups, categories, single_events, ical_events,
        recurring_events, ALLOWED_STATES, event_overrides=event_overrides
    )

    with open(os.path.join(DATA_DIR, 'all_events.json'), 'w') as f:
        json.dump(unique_events, f, indent=2)

    print(f"Generated data for {len(unique_events)} events")


if __name__ == "__main__":
    main()
