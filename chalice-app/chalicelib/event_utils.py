"""
Event processing utilities
"""
from typing import List, Dict, Any
from datetime import datetime, timedelta, date
import pytz


def is_virtual_event(event: Dict[str, Any]) -> bool:
    """
    Check if event is virtual

    Args:
        event: Event dictionary

    Returns:
        True if virtual, False otherwise
    """
    location = event.get('location', '').lower()
    location_type = event.get('location_type', '').lower()

    return (
        location_type == 'virtual' or
        'virtual' in location or
        'online' in location or
        'zoom' in location or
        'webinar' in location
    )


def filter_events_by_location(
    events: List[Dict[str, Any]],
    city: str = None,
    state: str = None
) -> List[Dict[str, Any]]:
    """
    Filter events by city and/or state

    Args:
        events: List of event dictionaries
        city: City name to filter by (optional)
        state: State abbreviation to filter by (optional)

    Returns:
        Filtered list of events
    """
    filtered = []

    for event in events:
        event_city = event.get('city', '')
        event_state = event.get('state', '')

        if city and state:
            if event_city.lower() == city.lower() and event_state == state:
                filtered.append(event)
        elif state:
            if event_state == state:
                filtered.append(event)
        elif city:
            if event_city.lower() == city.lower():
                filtered.append(event)
        else:
            filtered.append(event)

    return filtered


def get_week_identifier(date_str: str) -> str:
    """
    Get ISO week identifier for a date

    Args:
        date_str: Date string in YYYY-MM-DD or ISO 8601 format

    Returns:
        Week identifier in format YYYY-Www (e.g., 2026-W02)
    """
    try:
        # Handle ISO 8601 datetime format
        if 'T' in date_str:
            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')

        iso_calendar = date_obj.isocalendar()
        return f"{iso_calendar[0]}-W{iso_calendar[1]:02d}"

    except Exception as e:
        print(f"Error getting week identifier for {date_str}: {e}")
        return ""


def filter_events_by_week(
    events: List[Dict[str, Any]],
    week_id: str
) -> List[Dict[str, Any]]:
    """
    Filter events to only those in a specific ISO week

    Args:
        events: List of event dictionaries
        week_id: Week identifier in format YYYY-Www (e.g., 2026-W02)

    Returns:
        Filtered list of events in that week
    """
    week_events = []

    for event in events:
        start_date = event.get('start_datetime', '')
        event_week = get_week_identifier(start_date)

        if event_week == week_id:
            week_events.append(event)

    return week_events


def prepare_events_by_day(
    events: List[Dict[str, Any]],
    timezone: pytz.timezone
) -> List[Dict[str, Any]]:
    """
    Organize events by day and time slot

    Args:
        events: List of event dictionaries
        timezone: Timezone for date calculations

    Returns:
        List of day dictionaries with events organized by time slots
    """
    events_by_day = {}

    for event in events:
        # Parse start datetime
        start_datetime_str = event.get('start_datetime', '')
        end_datetime_str = event.get('end_datetime', '')

        if not start_datetime_str:
            continue

        try:
            # Parse ISO 8601 datetime
            if 'T' in start_datetime_str:
                start_dt = datetime.fromisoformat(start_datetime_str.replace('Z', '+00:00'))
                start_dt = start_dt.astimezone(timezone)
            else:
                # Just a date
                start_dt = datetime.strptime(start_datetime_str, '%Y-%m-%d')
                start_dt = timezone.localize(start_dt)

            start_date = start_dt.date()

            # Parse end datetime for multi-day events
            if end_datetime_str:
                if 'T' in end_datetime_str:
                    end_dt = datetime.fromisoformat(end_datetime_str.replace('Z', '+00:00'))
                    end_dt = end_dt.astimezone(timezone)
                else:
                    end_dt = datetime.strptime(end_datetime_str, '%Y-%m-%d')
                    end_dt = timezone.localize(end_dt)

                end_date = end_dt.date()
            else:
                end_date = start_date

        except Exception as e:
            print(f"Error parsing datetime for event {event.get('title')}: {e}")
            continue

        # Handle multi-day events
        current_date = start_date
        day_index = 0

        while current_date <= end_date:
            day_key = current_date.isoformat()

            # Create day entry if it doesn't exist
            if day_key not in events_by_day:
                events_by_day[day_key] = {
                    'date': day_key,
                    'date_obj': current_date,
                    'day_name': current_date.strftime('%A'),
                    'day_number': current_date.day,
                    'month_name': current_date.strftime('%B'),
                    'year': current_date.year,
                    'time_slots': {}
                }

            # Determine time slot
            time_key = 'All Day'
            if 'T' in start_datetime_str and ':' in start_datetime_str:
                time_key = start_dt.strftime('%H:%M')

            # Create event copy for this day
            event_copy = event.copy()

            # Add display_title with (continuing) for multi-day events
            if day_index > 0:
                event_copy['display_title'] = f"{event['title']} (continuing)"
            else:
                event_copy['display_title'] = event['title']

            # Create time slot if it doesn't exist
            if time_key not in events_by_day[day_key]['time_slots']:
                events_by_day[day_key]['time_slots'][time_key] = []

            events_by_day[day_key]['time_slots'][time_key].append(event_copy)

            current_date += timedelta(days=1)
            day_index += 1

    # Convert to sorted list of days
    sorted_days = sorted(events_by_day.keys())
    days_data = []

    for day in sorted_days:
        day_data = events_by_day[day]

        # Sort time slots
        time_slots = []

        def time_sort_key(time_str):
            if time_str == 'All Day':
                return (-1, 0)
            try:
                hour, minute = map(int, time_str.split(':'))
                return (hour, minute)
            except:
                return (0, 0)

        sorted_times = sorted(day_data['time_slots'].keys(), key=time_sort_key)

        for time in sorted_times:
            time_slots.append({
                'time': time,
                'events': sorted(
                    day_data['time_slots'][time],
                    key=lambda x: x.get('title', '')
                )
            })

        day_data['time_slots'] = time_slots
        day_data['has_events'] = bool(time_slots)
        days_data.append(day_data)

    return days_data


def parse_event_datetime(
    date_str: str,
    time_str: str = None,
    timezone: pytz.timezone = None
) -> datetime:
    """
    Parse event date and time into datetime object

    Args:
        date_str: Date string (YYYY-MM-DD)
        time_str: Time string (HH:MM) (optional)
        timezone: Timezone object (optional)

    Returns:
        Datetime object
    """
    if timezone is None:
        timezone = pytz.UTC

    try:
        # Parse date
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')

        # Add time if provided
        if time_str:
            time_parts = time_str.split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            date_obj = date_obj.replace(hour=hour, minute=minute)

        # Localize to timezone
        return timezone.localize(date_obj)

    except Exception as e:
        print(f"Error parsing datetime {date_str} {time_str}: {e}")
        return timezone.localize(datetime.now())
