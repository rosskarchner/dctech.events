"""
iCal feed generation
"""
from typing import List, Dict, Any
from datetime import datetime
import pytz
from icalendar import Calendar, Event as ICalEvent
import hashlib


def generate_ical_feed(
    events: List[Dict[str, Any]],
    site_name: str,
    base_url: str,
    timezone: pytz.timezone
) -> str:
    """
    Generate iCal feed from events

    Args:
        events: List of event dictionaries
        site_name: Site name for calendar
        base_url: Base URL for event links
        timezone: Timezone for events

    Returns:
        iCal feed as string
    """
    cal = Calendar()

    # Calendar properties
    cal.add('prodid', f'-//{site_name}//EN')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', site_name)
    cal.add('x-wr-timezone', str(timezone))

    # Add each event
    for event_data in events:
        event = ICalEvent()

        # Event title
        title = event_data.get('title', 'Untitled Event')
        event.add('summary', title)

        # Event description
        description = event_data.get('description', '')
        event.add('description', description)

        # Event URL
        url = event_data.get('url', '')
        if url:
            event.add('url', url)

        # Location
        location = event_data.get('location', '')
        event.add('location', location)

        # Start datetime
        start_datetime_str = event_data.get('start_datetime', '')
        if start_datetime_str:
            try:
                if 'T' in start_datetime_str:
                    start_dt = datetime.fromisoformat(start_datetime_str.replace('Z', '+00:00'))
                    start_dt = start_dt.astimezone(timezone)
                else:
                    # All-day event
                    start_dt = datetime.strptime(start_datetime_str, '%Y-%m-%d').date()

                event.add('dtstart', start_dt)

            except Exception as e:
                print(f"Error parsing start datetime for {title}: {e}")
                continue

        # End datetime
        end_datetime_str = event_data.get('end_datetime', '')
        if end_datetime_str:
            try:
                if 'T' in end_datetime_str:
                    end_dt = datetime.fromisoformat(end_datetime_str.replace('Z', '+00:00'))
                    end_dt = end_dt.astimezone(timezone)
                else:
                    # All-day event
                    end_dt = datetime.strptime(end_datetime_str, '%Y-%m-%d').date()

                event.add('dtend', end_dt)

            except Exception as e:
                print(f"Error parsing end datetime for {title}: {e}")

        # UID - use event_id or generate from event data
        uid = event_data.get('event_id')
        if not uid:
            # Generate UID from event data
            uid_str = f"{title}{start_datetime_str}{url}".encode('utf-8')
            uid = hashlib.sha256(uid_str).hexdigest()

        event.add('uid', f"{uid}@{base_url}")

        # Timestamp
        event.add('dtstamp', datetime.now(timezone))

        # Organizer (group)
        group_name = event_data.get('group_name', '')
        if group_name:
            event.add('organizer', group_name)

        # Add event to calendar
        cal.add_component(event)

    # Return iCal string
    return cal.to_ical().decode('utf-8')
