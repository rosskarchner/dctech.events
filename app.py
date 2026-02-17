from flask import Flask, render_template, request, Response, send_from_directory
from datetime import date, datetime, timedelta, time
import os
import yaml
import pytz
import calendar
import json
from pathlib import Path
from location_utils import extract_location_info, get_region_name
import io
from icalendar import Calendar, Event as ICalEvent
import hashlib
from xml.etree import ElementTree as ET
from email.utils import formatdate
import db_utils
import dynamo_data

# Load configuration
CONFIG_FILE = 'config.yaml'
config = {}
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r') as f:
        config = yaml.safe_load(f)

# Define timezone from config
timezone_name = config.get('timezone', 'US/Eastern')
local_tz = pytz.timezone(timezone_name)

# Get site configuration
SITE_NAME = config.get('site_name', 'DC Tech Events')
TAGLINE = config.get('tagline', 'Technology conferences and meetups in and around Washington, DC')
BASE_URL = config.get('base_url', 'https://dctech.events')
ADD_EVENTS_LINK = config.get('add_events_link', 'https://add.dctech.events')
NEWSLETTER_SIGNUP_LINK = config.get('newsletter_signup_link', 'https://newsletter.dctech.events')

# Constants - data paths
DATA_DIR = '_data'
SPONSORS_FILE = os.path.join(DATA_DIR, 'sponsors.json')

app = Flask(__name__, template_folder='templates')

def load_sponsors():
    """Load sponsors from sponsors.json file"""
    if not SPONSORS_FILE or not os.path.exists(SPONSORS_FILE):
        return []

    try:
        with open(SPONSORS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading sponsors: {e}")
        return []

@app.context_processor
def inject_config():
    """Inject configuration variables into all templates"""
    context = {
        'site_name': SITE_NAME,
        'tagline': TAGLINE,
        'base_url': BASE_URL,
        'add_events_link': ADD_EVENTS_LINK,
        'newsletter_signup_link': NEWSLETTER_SIGNUP_LINK,
        'sponsors': load_sponsors(),
        'categories': get_categories()
    }

    return context

def get_events(include_hidden=False):
    """
    Get events from DynamoDB

    Args:
        include_hidden: If True, include events marked as hidden. Default False.

    Returns:
        A list of events
    """
    events = db_utils.get_future_events()

    # Sort by date and time (since DynamoDB only sorts by date)
    # Ensure date and time are strings
    events.sort(key=lambda x: (str(x.get('date', '')), str(x.get('time', ''))))

    # Filter out hidden events unless explicitly requested
    if not include_hidden:
        events = [e for e in events if not e.get('hidden', False)]

    return events

def get_approved_groups():
    """
    Get all groups from DynamoDB.

    Returns:
        A list of group dictionaries
    """
    groups = dynamo_data.get_all_groups()
    groups.sort(key=lambda x: x.get('name', '').lower())
    return groups

def get_categories():
    """
    Get all categories from DynamoDB.

    Returns:
        A dict mapping category slugs to category metadata
        Example: {'python': {'name': 'Python', 'description': '...', 'slug': 'python'}, ...}
    """
    return dynamo_data.get_all_categories()

def get_upcoming_months():
    """
    Get a list of upcoming months that have events.
    
    Returns:
        List of dictionaries with month information:
        - year: Year (int)
        - month: Month number (int)
        - name: Month name (e.g., "February 2026")
        - count: Number of events in that month
        - url: URL to the month page
    """
    events = get_events()
    months = {}
    
    for event in events:
        event_date_str = event.get('date')
        if not event_date_str:
            continue
        
        try:
            event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
            month_key = (event_date.year, event_date.month)
            
            if month_key not in months:
                month_name = calendar.month_name[event_date.month]
                months[month_key] = {
                    'year': event_date.year,
                    'month': event_date.month,
                    'name': f"{month_name} {event_date.year}",
                    'count': 0,
                    'url': f"/{event_date.year}/{event_date.month}/"
                }
            
            months[month_key]['count'] += 1
        except ValueError:
            continue
    
    # Return sorted by year and month
    return [months[k] for k in sorted(months.keys())]

def get_categories_with_event_counts():
    """
    Get categories that have upcoming events, sorted by event count.
    
    Returns:
        List of dictionaries with category information:
        - slug: Category slug
        - name: Category name
        - count: Number of upcoming events
        - url: URL to the category page
    """
    categories = get_categories()
    events = get_events()
    
    categories_with_counts = []
    for slug, category in categories.items():
        filtered_events = [e for e in events if slug in e.get('categories', [])]
        count = len(filtered_events)
        
        if count > 0:
            categories_with_counts.append({
                'slug': slug,
                'name': category['name'],
                'count': count,
                'url': f"/categories/{slug}/"
            })
    
    # Sort by count descending
    categories_with_counts.sort(key=lambda x: x['count'], reverse=True)
    
    return categories_with_counts

def filter_events_to_next_two_weeks(events):
    """
    Filter events to the next 14 days.
    
    Args:
        events: List of event dictionaries
    
    Returns:
        List of events occurring within the next 14 days
    """
    today = date.today()
    two_weeks_from_now = today + timedelta(days=14)
    return [
        e for e in events 
        if e.get('date') and datetime.strptime(e['date'], '%Y-%m-%d').date() <= two_weeks_from_now
    ]

def calculate_event_hash(date, time, title, url=None):
    """
    Calculate MD5 hash for event identification.
    Matches iCal GUID generation algorithm in generate_month_data.py.
    
    Args:
        date: Event date (YYYY-MM-DD format)
        time: Event time (HH:MM format, or empty string)
        title: Event title
        url: Optional event URL
    
    Returns:
        MD5 hash string (hex)
    """
    uid_parts = [date, time, title]
    if url:
        uid_parts.append(url)
    
    uid_base = '-'.join(str(p) for p in uid_parts)
    uid_hash = hashlib.md5(uid_base.encode('utf-8')).hexdigest()
    return uid_hash

def prepare_events_by_day(events, add_week_links=False):
    """
    Organize events by day and time

    Args:
        events: List of event dictionaries
        add_week_links: Whether to add week page URLs to each day (default False)

    Returns:
        List of days with events, each day is a dictionary with date, short_date, and time_slots
    """
    # Create a dictionary to store events by day
    events_by_day = {}

    # Add events to their respective days
    for event in events:
        day_key = event.get('date')
        if not day_key:
            continue

        # Parse the start date and end date if it exists
        start_date = datetime.strptime(day_key, '%Y-%m-%d').date()
        end_date = None
        if 'end_date' in event:
            try:
                end_date = datetime.strptime(event['end_date'], '%Y-%m-%d').date()
            except ValueError:
                pass

        # Generate list of dates for this event
        event_dates = []
        if end_date and end_date > start_date:
            current_date = start_date
            while current_date <= end_date:
                event_dates.append(current_date)
                current_date += timedelta(days=1)
        else:
            event_dates = [start_date]

        # Add event to each day
        for i, event_date in enumerate(event_dates):
            day_key = event_date.strftime('%Y-%m-%d')
            short_date = event_date.strftime('%a %-m/%-d')  # Format as "Mon 5/5"

            if day_key not in events_by_day:
                week_url = None
                if add_week_links:
                    week_id = get_week_identifier(event_date)
                    week_url = f"/week/{week_id}/#{day_key}"

                events_by_day[day_key] = {
                    'date': day_key,
                    'short_date': short_date,
                    'week_url': week_url,
                    'time_slots': {}
                }

            # Determine the time for this specific day
            time_key = 'All Day'
            formatted_time = 'All Day'
            original_time = event.get('time', '')
            
            # Check if time is a dictionary (per-day times)
            if isinstance(original_time, dict):
                # Use the time for this specific date if available
                original_time = original_time.get(day_key, '')
            
            # Only try to parse time if it exists and is a string
            if original_time and isinstance(original_time, str):
                try:
                    # Handle time parsing - only do this if time is in HH:MM format
                    if ':' in original_time:
                        time_obj = datetime.strptime(original_time.strip(), '%H:%M').time()
                        # For time_key, use the original HH:MM format for consistent sorting
                        time_key = time_obj.strftime('%H:%M')
                        # For display, use am/pm format
                        formatted_time = time_obj.strftime('%-I:%M %p').lower()  # Format as "1:30 pm"
                except ValueError:
                    # If time parsing fails, keep All Day
                    pass

            # Create a copy of the event for this day
            event_copy = event.copy()
            # Store the machine-readable time (HH:MM format) for datetime attribute
            event_copy['time'] = time_key if time_key != 'All Day' else ''
            # Store the formatted time for display
            event_copy['formatted_time'] = formatted_time

            # Add display_title with (continuing) for days after the first
            if i > 0:
                event_copy['display_title'] = f"{event['title']} (continuing)"
            else:
                event_copy['display_title'] = event['title']

            # Create time slot if it doesn't exist
            if time_key not in events_by_day[day_key]['time_slots']:
                events_by_day[day_key]['time_slots'][time_key] = []

            events_by_day[day_key]['time_slots'][time_key].append(event_copy)

    # Convert the dictionary to a sorted list of days
    sorted_days = sorted(events_by_day.keys())
    days_data = []

    for day in sorted_days:
        day_data = events_by_day[day]
        # Sort events within each time slot
        time_slots = []

        # Custom sort function for time values
        def time_sort_key(time_str):
            if time_str == 'All Day':
                return (-1, 0)  # Put All Day (events without time) at the beginning
            try:
                # Parse time in HH:MM format (24-hour)
                hour, minute = map(int, time_str.split(':'))
                return (hour, minute)
            except:
                return (0, 0)  # Default case

        sorted_times = sorted(day_data['time_slots'].keys(), key=time_sort_key)

        for time in sorted_times:
            time_slots.append({
                'time': time,
                'events': sorted(day_data['time_slots'][time], key=lambda x: x.get('title', ''))
            })

        day_data['time_slots'] = time_slots
        day_data['has_events'] = bool(time_slots)  # True if there are any time slots with events
        days_data.append(day_data)

    return days_data

def get_stats():
    """
    Load statistics from stats.yaml
    
    Returns:
        Dictionary containing stats, or empty dict if file doesn't exist
    """
    stats_file = os.path.join(DATA_DIR, 'stats.yaml')
    if not os.path.exists(stats_file):
        return {}
    
    try:
        with open(stats_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Error loading stats: {e}")
        return {}

def filter_events_by_location(events, city=None, state=None):
    """
    Filter events by city and/or state.

    Args:
        events: List of event dictionaries
        city: City name to filter by (optional)
        state: State abbreviation to filter by (optional)

    Returns:
        Filtered list of events
    """
    filtered = []
    for event in events:
        event_city, event_state = extract_location_info(event.get('location', ''))

        if city and state:
            if event_city and event_state and event_city.lower() == city.lower() and event_state == state:
                filtered.append(event)
        elif state:
            if event_state == state:
                filtered.append(event)
        elif city:
            if event_city and event_city.lower() == city.lower():
                filtered.append(event)

    return filtered

def is_virtual_event(event):
    """
    Determine if an event is virtual based on its location_type field.
    
    Args:
        event: Event dictionary
    
    Returns:
        True if event is virtual, False otherwise
    """
    return event.get('location_type') == 'virtual'

def filter_virtual_events(events):
    """
    Filter events to return only virtual events.
    
    Args:
        events: List of event dictionaries
    
    Returns:
        List of virtual events
    """
    return [event for event in events if is_virtual_event(event)]

def filter_in_person_events(events):
    """
    Filter events to return only in-person events (non-virtual).
    
    Args:
        events: List of event dictionaries
    
    Returns:
        List of in-person events
    """
    return [event for event in events if not is_virtual_event(event)]

def get_iso_week_dates(year, week):
    """
    Get the start and end dates for an ISO week.
    ISO weeks start on Monday and end on Sunday.

    Args:
        year: ISO year
        week: ISO week number (1-53)

    Returns:
        Tuple of (start_date, end_date) for the week
    """
    # January 4th is always in week 1
    jan4 = date(year, 1, 4)
    week_1_monday = jan4 - timedelta(days=jan4.weekday())

    # Calculate the Monday of the target week
    week_start = week_1_monday + timedelta(weeks=week - 1)
    week_end = week_start + timedelta(days=6)

    return week_start, week_end

def get_week_identifier(target_date):
    """
    Get the ISO week identifier (YYYY-Www) for a given date.

    Args:
        target_date: A date object

    Returns:
        String in format YYYY-Www (e.g., "2024-W45")
    """
    iso_year, iso_week, _ = target_date.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"

def parse_week_identifier(week_id):
    """
    Parse a week identifier string into year and week number.

    Args:
        week_id: String in format YYYY-Www (e.g., "2024-W45")

    Returns:
        Tuple of (year, week_number)
    """
    parts = week_id.split('-W')
    year = int(parts[0])
    week = int(parts[1])
    return year, week

def filter_events_by_week(events, week_start, week_end):
    """
    Filter events that occur within a specific week.

    Args:
        events: List of event dictionaries
        week_start: Start date of the week (Monday)
        week_end: End date of the week (Sunday)

    Returns:
        Filtered list of events
    """
    filtered = []
    for event in events:
        event_date_str = event.get('date')
        if not event_date_str:
            continue

        try:
            event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()

            # Check if event has an end date
            end_date = event_date
            if 'end_date' in event:
                try:
                    end_date = datetime.strptime(event['end_date'], '%Y-%m-%d').date()
                except ValueError:
                    pass

            # Include event if it overlaps with the week
            if (event_date <= week_end and end_date >= week_start):
                filtered.append(event)
        except ValueError:
            continue

    return filtered

def filter_events_by_month(events, month_start, month_end):
    """
    Filter events that occur within a specific month.

    Args:
        events: List of event dictionaries
        month_start: First day of the month
        month_end: Last day of the month

    Returns:
        Filtered list of events
    """
    filtered = []
    for event in events:
        event_date_str = event.get('date')
        if not event_date_str:
            continue

        try:
            event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()

            # Check if event has an end date
            end_date = event_date
            if 'end_date' in event:
                try:
                    end_date = datetime.strptime(event['end_date'], '%Y-%m-%d').date()
                except ValueError:
                    pass

            # Include event if it overlaps with the month
            if (event_date <= month_end and end_date >= month_start):
                filtered.append(event)
        except ValueError:
            continue

    return filtered

def get_upcoming_weeks(num_weeks=12):
    """
    Get a list of upcoming ISO week identifiers.
    """
    weeks = set()
    current_date = date.today()

    # Add the next num_weeks from today (rolling window)
    for i in range(num_weeks):
        week_date = current_date + timedelta(weeks=i)
        week_id = get_week_identifier(week_date)
        weeks.add(week_id)

    # Add weeks for all events
    events = get_events()
    for event in events:
        # Get start date
        event_date_str = event.get('date')
        if event_date_str:
            try:
                event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
                week_id = get_week_identifier(event_date)
                weeks.add(week_id)
                
                # Get end date if it exists (for multi-day events)
                end_date_str = event.get('end_date')
                if end_date_str:
                    try:
                        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                        # Add all weeks between start and end date (inclusive)
                        current = event_date
                        while current <= end_date:
                            week_id = get_week_identifier(current)
                            weeks.add(week_id)
                            current += timedelta(days=1)
                    except (ValueError, TypeError):
                        pass
            except (ValueError, TypeError):
                pass

    return sorted(list(weeks))

@app.route("/robots.txt")
def robots_txt():
    """Serve robots.txt from the static folder"""
    return send_from_directory(app.static_folder, 'robots.txt')

@app.route("/")
def homepage():
    # Get upcoming events and filter out virtual events
    all_events = get_events()
    events = filter_in_person_events(all_events)
    
    # Filter to next two weeks
    two_week_events = filter_events_to_next_two_weeks(events)
    
    days = prepare_events_by_day(two_week_events, add_week_links=True)

    # Get base URL from config or use a default
    base_url = BASE_URL

    # Get stats - count only in-person events in next two weeks
    stats = get_stats().copy()
    stats['upcoming_events'] = len(two_week_events)
    stats['total_upcoming_events'] = len(events)
    
    # Get upcoming months with event counts
    upcoming_months = get_upcoming_months()
    
    # Get categories with event counts
    categories_with_counts = get_categories_with_event_counts()
    
    # Get recently added events for preview
    recently_added = get_recently_added_events(limit=5)
    
    return render_template('homepage.html',
                          days=days,
                          stats=stats,
                          base_url=base_url,
                          upcoming_months=upcoming_months,
                          categories_with_counts=categories_with_counts,
                          recently_added=recently_added)

@app.route("/virtual/")
def virtual_events_page():
    """Show virtual events"""
    # Get upcoming events and filter to only virtual events
    all_events = get_events()
    events = filter_virtual_events(all_events)
    days = prepare_events_by_day(events, add_week_links=False)

    # Get base URL from config or use a default
    base_url = BASE_URL

    # Get stats for virtual events only
    stats = {'upcoming_events': len(events)}
    
    return render_template('virtual_events.html',
                          days=days,
                          stats=stats,
                          base_url=base_url)

@app.route("/week/<week_id>/")
def week_page(week_id):
    """Show events for a specific ISO week"""
    try:
        year, week_num = parse_week_identifier(week_id)
        week_start, week_end = get_iso_week_dates(year, week_num)
    except:
        return "Invalid week identifier", 404

    # Get all events and filter by week
    events = get_events()
    week_events = filter_events_by_week(events, week_start, week_end)
    days = prepare_events_by_day(week_events)

    # Format week start for display
    week_start_formatted = week_start.strftime('%B %-d, %Y')

    # Get stats
    stats = {'upcoming_events': len(week_events)}

    # Get base URL
    base_url = config.get('base_url', 'https://dctech.events')

    return render_template('week_page.html',
                          days=days,
                          stats=stats,
                          week_id=week_id,
                          week_start=week_start,
                          week_end=week_end,
                          week_start_formatted=week_start_formatted,
                          base_url=base_url)

@app.route("/<int:year>/<int:month>/")
def month_page(year, month):
    """Show events for a specific month"""
    try:
        # Validate month
        if month < 1 or month > 12:
            return "Invalid month", 404
        
        # Get the first and last day of the month
        first_day = date(year, month, 1)
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)
        
    except ValueError:
        return "Invalid date", 404
    
    # Get all events and filter by month
    events = get_events()
    month_events = filter_events_by_month(events, first_day, last_day)
    days = prepare_events_by_day(month_events)
    
    # Get month name
    month_name = calendar.month_name[month]
    
    # Get stats
    stats = {'upcoming_events': len(month_events)}
    
    # Calculate previous and next month
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year
    
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year
    
    return render_template('month_page.html',
                          days=days,
                          stats=stats,
                          month_name=month_name,
                          year=year,
                          prev_month=prev_month,
                          prev_year=prev_year,
                          next_month=next_month,
                          next_year=next_year)

@app.route("/locations/")
def locations_index():
    """Show available regions with event counts"""
    events = get_events()
    
    # Count events by region only
    location_stats = {}
    
    for event in events:
        city, state = extract_location_info(event.get('location', ''))
        if state in ['DC', 'VA', 'MD']:
            region = get_region_name(state)
            location_stats[region] = location_stats.get(region, 0) + 1
    
    return render_template('locations_index.html',
                          location_stats=location_stats,
                          city_stats={})

@app.route("/groups/")
def approved_groups_list():
    # Get all groups
    groups = get_approved_groups()
    
    return render_template('approved_groups_list.html', 
                          groups=groups, 
                          next_key=None,
                          has_next=False)

@app.route("/newsletter.html")
def newsletter_html():
    # Get upcoming events
    events = get_events()
    
    # Filter to next two weeks (14 days)
    two_week_events = filter_events_to_next_two_weeks(events)
    
    days = prepare_events_by_day(two_week_events)
    
    # Get stats
    stats = get_stats().copy()
    stats['upcoming_events'] = len(two_week_events)
    
    # Get upcoming months with event counts
    upcoming_months = get_upcoming_months()
    
    # Get categories with event counts
    categories_with_counts = get_categories_with_event_counts()
    
    return render_template('newsletter.html',
                          days=days,
                          stats=stats,
                          base_url=BASE_URL,
                          upcoming_months=upcoming_months,
                          categories_with_counts=categories_with_counts)

@app.route("/newsletter.txt")
def newsletter_text():
    # Get upcoming events
    events = get_events()
    
    # Filter to next two weeks (14 days)
    two_week_events = filter_events_to_next_two_weeks(events)
    
    days = prepare_events_by_day(two_week_events)
    
    # Get stats
    stats = get_stats().copy()
    stats['upcoming_events'] = len(two_week_events)
    
    # Get upcoming months with event counts
    upcoming_months = get_upcoming_months()
    
    # Get categories with event counts
    categories_with_counts = get_categories_with_event_counts()
    
    response = render_template('newsletter.txt',
                             days=days,
                             stats=stats,
                             base_url=BASE_URL,
                             upcoming_months=upcoming_months,
                             categories_with_counts=categories_with_counts)
    return response, 200, {'Content-Type': 'text/plain; charset=utf-8'}

@app.route("/locations/<state>/")
def region_page(state):
    """Show events for a specific state/region"""
    state = state.upper()
    if state not in ['DC', 'VA', 'MD']:
        return "Region not found", 404

    events = get_events()
    filtered_events = filter_events_by_location(events, state=state)
    days = prepare_events_by_day(filtered_events)
    
    region_name = get_region_name(state)
    stats = {'upcoming_events': len(filtered_events)}
    
    return render_template('location_page.html',
                          days=days,
                          stats=stats,
                          location_name=region_name,
                          location_type='region')

@app.route("/categories/")
def categories_index():
    """Show listing of all categories with event counts"""
    categories = get_categories()
    events = get_events()
    
    categories_with_counts = []
    for slug, category in sorted(categories.items(), key=lambda x: x[1]['name']):
        filtered_events = [e for e in events if slug in e.get('categories', [])]
        categories_with_counts.append({
            'slug': slug,
            'name': category['name'],
            'description': category.get('description', ''),
            'count': len(filtered_events)
        })
    
    return render_template('categories_index.html', categories=categories_with_counts)

@app.route("/categories/<slug>/")
def category_page(slug):
    """Show events for a specific category"""
    categories = get_categories()
    if slug not in categories:
        return "Category not found", 404

    events = get_events()
    filtered_events = [e for e in events if slug in e.get('categories', [])]
    days = prepare_events_by_day(filtered_events)

    category = categories[slug]
    stats = {'upcoming_events': len(filtered_events)}

    return render_template('category_page.html',
                         days=days,
                         stats=stats,
                         category_name=category['name'],
                         category_description=category.get('description', ''))

@app.route("/feeds/")
def feeds_page():
    """Show a page listing all available RSS and iCal feeds"""
    categories = get_categories()
    events = get_events()
    
    # Get categories with event counts
    categories_with_counts = []
    for slug, category in sorted(categories.items(), key=lambda x: x[1]['name']):
        filtered_events = [e for e in events if slug in e.get('categories', [])]
        count = len(filtered_events)
        if count > 0:
            categories_with_counts.append({
                'slug': slug,
                'name': category['name'],
                'count': count
            })
    
    # Define locations
    locations = [
        {'state': 'dc', 'name': 'District of Columbia'},
        {'state': 'md', 'name': 'Maryland'},
        {'state': 'va', 'name': 'Virginia'}
    ]
    
    return render_template('feeds.html',
                         categories=categories_with_counts,
                         locations=locations)

@app.route("/sitemap.xml")
def sitemap():
    """Generate an XML sitemap of the site's main pages"""
    base_url = config.get('base_url', 'https://dctech.events')

    urls = [
        {'loc': f"{base_url}/", 'lastmod': datetime.now().strftime('%Y-%m-%d')},
        {'loc': f"{base_url}/virtual/", 'lastmod': datetime.now().strftime('%Y-%m-%d')},
        {'loc': f"{base_url}/categories/", 'lastmod': datetime.now().strftime('%Y-%m-%d')},
        {'loc': f"{base_url}/groups/", 'lastmod': datetime.now().strftime('%Y-%m-%d')},
        {'loc': f"{base_url}/locations/", 'lastmod': datetime.now().strftime('%Y-%m-%d')},
        {'loc': f"{base_url}/locations/dc/", 'lastmod': datetime.now().strftime('%Y-%m-%d')},
        {'loc': f"{base_url}/locations/va/", 'lastmod': datetime.now().strftime('%Y-%m-%d')},
        {'loc': f"{base_url}/locations/md/", 'lastmod': datetime.now().strftime('%Y-%m-%d')},
    ]

    categories = get_categories()
    for slug in categories.keys():
        urls.append({
            'loc': f"{base_url}/categories/{slug}/",
            'lastmod': datetime.now().strftime('%Y-%m-%d'),
            'changefreq': 'daily'
        })

    upcoming_weeks = get_upcoming_weeks(12)
    for week_id in upcoming_weeks:
        urls.append({
            'loc': f"{base_url}/week/{week_id}/",
            'lastmod': datetime.now().strftime('%Y-%m-%d'),
            'changefreq': 'daily'
        })

    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    for url in urls:
        xml.append('  <url>')
        xml.append(f'    <loc>{url["loc"]}</loc>')
        xml.append(f'    <lastmod>{url["lastmod"]}</lastmod>')
        changefreq = url.get('changefreq', 'daily')
        xml.append(f'    <changefreq>{changefreq}</changefreq>')
        xml.append('  </url>')

    xml.append('</urlset>')

    return Response('\n'.join(xml), mimetype='text/xml')

@app.route("/events.json")
def events_json():
    """Serve events data as JSON for client-side use"""
    events_json_file = os.path.join(DATA_DIR, 'events.json')
    if os.path.exists(events_json_file):
        with open(events_json_file, 'r', encoding='utf-8') as f:
            return Response(f.read(), mimetype='application/json')
    # Fallback: return current events if JSON doesn't exist yet
    events = get_events()
    return Response(json.dumps(events, indent=2), mimetype='application/json')

@app.route("/events.ics")
def ical_feed():
    """Generate an iCal feed of upcoming events"""
    events = get_events()
    return generate_ical_feed(events, SITE_NAME, TAGLINE)

def generate_ical_feed(filtered_events, calendar_name, calendar_description):
    """
    Helper function to generate an iCal feed for a filtered set of events
    """
    groups = get_approved_groups()
    group_websites = {group.get('name'): group.get('website') for group in groups if group.get('website')}
    
    cal = Calendar()
    cal.add('prodid', f'-//{SITE_NAME}//dctech.events//')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', calendar_name)
    cal.add('x-wr-caldesc', calendar_description)
    
    for event in filtered_events:
        event_date_str = event.get('date')
        if not event_date_str:
            continue
        
        try:
            event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            continue
        
        event_time_str = event.get('time', '')
        is_all_day = not (event_time_str and isinstance(event_time_str, str) and ':' in event_time_str)
        
        if is_all_day:
            event_datetime = event_date
            end_date_str = event.get('end_date')
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                    end_datetime = end_date + timedelta(days=1)
                except (ValueError, TypeError):
                    end_datetime = event_date + timedelta(days=1)
            else:
                end_datetime = event_date + timedelta(days=1)
        else:
            try:
                event_time = datetime.strptime(event_time_str.strip(), '%H:%M').time()
            except ValueError:
                event_datetime = event_date
                end_datetime = event_date + timedelta(days=1)
                is_all_day = True
            
            if not is_all_day:
                event_datetime_local = datetime.combine(event_date, event_time)
                event_datetime_local = local_tz.localize(event_datetime_local)
                event_datetime = event_datetime_local.astimezone(pytz.UTC)
                
                end_date_str = event.get('end_date')
                if end_date_str:
                    try:
                        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                        end_time = datetime.strptime('23:59', '%H:%M').time()
                        end_datetime_local = datetime.combine(end_date, end_time)
                        end_datetime_local = local_tz.localize(end_datetime_local)
                        end_datetime = end_datetime_local.astimezone(pytz.UTC)
                    except (ValueError, TypeError):
                        end_datetime = event_datetime + timedelta(hours=1)
                else:
                    end_datetime = event_datetime + timedelta(hours=1)
        
        ical_event = ICalEvent()
        ical_event.add('summary', event.get('title', 'Untitled Event'))
        ical_event.add('dtstart', event_datetime)
        ical_event.add('dtend', end_datetime)
        
        if event.get('location'):
            ical_event.add('location', event['location'])
        
        description_parts = []
        if event.get('url'):
            description_parts.append(f"Event URL: {event['url']}")
        if event.get('group'):
            description_parts.append(f"Organized by: {event['group']}")
        if event.get('cost'):
            description_parts.append(f"Cost: {event['cost']}")
        if description_parts:
            ical_event.add('description', '\n'.join(description_parts))
        
        if event.get('url'):
            ical_event.add('url', event['url'])
        
        if event.get('group'):
            group_name = event['group']
            group_website = group_websites.get(group_name)
            if group_website:
                ical_event.add('organizer', group_website, parameters={'CN': group_name})
        
        uid_parts = [event_date_str, event_time_str, event.get('title', 'event')]
        if event.get('url'):
            uid_parts.append(event['url'])

        uid_base = '-'.join(str(p) for p in uid_parts)
        uid_hash = hashlib.md5(uid_base.encode('utf-8')).hexdigest()
        uid = f"{uid_hash}@dctech.events"
        ical_event.add('uid', uid)
        ical_event.add('dtstamp', datetime.now(pytz.UTC))
        cal.add_component(ical_event)
    
    return Response(cal.to_ical(), mimetype='text/calendar')

@app.route("/categories/<slug>/feed.ics")
def category_ical_feed(slug):
    """Generate an iCal feed for a specific category"""
    categories = get_categories()
    if slug not in categories:
        return "Category not found", 404
    
    events = get_events()
    filtered_events = [e for e in events if slug in e.get('categories', [])]
    
    category = categories[slug]
    calendar_name = f"{category['name']} Events - {SITE_NAME}"
    calendar_description = f"{category['name']} technology events in and around Washington, DC"
    
    return generate_ical_feed(filtered_events, calendar_name, calendar_description)

@app.route("/locations/<state>/feed.ics")
def location_ical_feed(state):
    """Generate an iCal feed for a specific location"""
    state = state.upper()
    if state not in ['DC', 'VA', 'MD']:
        return "Region not found", 404
    
    events = get_events()
    filtered_events = filter_events_by_location(events, state=state)
    
    region_name = get_region_name(state)
    calendar_name = f"{region_name} Events - {SITE_NAME}"
    calendar_description = f"Technology events in {region_name}"
    
    return generate_ical_feed(filtered_events, calendar_name, calendar_description)

def generate_rss_feed_from_events(events, feed_title, feed_description, feed_link):
    """
    Generate RSS 2.0 feed from a list of events.
    """
    rss = ET.Element('rss', version='2.0')
    rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')
    
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = feed_title
    ET.SubElement(channel, 'link').text = feed_link
    ET.SubElement(channel, 'description').text = feed_description
    ET.SubElement(channel, 'language').text = 'en-us'
    
    now_timestamp = datetime.now(pytz.UTC).timestamp()
    now_rfc822 = formatdate(timeval=now_timestamp, usegmt=True)
    ET.SubElement(channel, 'lastBuildDate').text = now_rfc822
    
    for event in events[:50]:
        item = ET.SubElement(channel, 'item')
        
        title = event.get('title', 'Untitled Event')
        event_date = event.get('date', '')
        event_time = event.get('time', '')
        url = event.get('url', '')
        
        if event_date:
            try:
                date_obj = datetime.strptime(event_date, '%Y-%m-%d').date()
                date_str = date_obj.strftime('%B %-d, %Y')
                full_title = f"{title} ({date_str})"
            except (ValueError, AttributeError):
                full_title = title
        else:
            full_title = title
        
        ET.SubElement(item, 'title').text = full_title
        link_url = url if url else BASE_URL
        ET.SubElement(item, 'link').text = link_url
        
        desc_parts = []
        if event_date:
            try:
                date_obj = datetime.strptime(event_date, '%Y-%m-%d').date()
                date_str = date_obj.strftime('%B %-d, %Y')
                if event_time:
                    desc_parts.append(f"Event Date: {date_str} at {event_time}")
                else:
                    desc_parts.append(f"Event Date: {date_str}")
            except (ValueError, AttributeError):
                pass
        
        if url:
            desc_parts.append(f'<a href="{url}">Event Details</a>')
        
        description = '<br/>'.join(desc_parts) if desc_parts else title
        ET.SubElement(item, 'description').text = description
        
        guid_text = f"{event_date}-{event_time}-{title}-{url}"
        guid_hash = hashlib.md5(guid_text.encode('utf-8')).hexdigest()
        guid = ET.SubElement(item, 'guid')
        guid.set('isPermaLink', 'false')
        guid.text = guid_hash
        
        if event_date:
            try:
                date_obj = datetime.strptime(event_date, '%Y-%m-%d')
                local_dt = local_tz.localize(date_obj)
                pub_timestamp = local_dt.astimezone(pytz.UTC).timestamp()
                pub_date_rfc822 = formatdate(timeval=pub_timestamp, usegmt=True)
                ET.SubElement(item, 'pubDate').text = pub_date_rfc822
            except (ValueError, AttributeError):
                pass
    
    tree = ET.ElementTree(rss)
    ET.indent(tree, space='  ')
    output = io.BytesIO()
    tree.write(output, encoding='utf-8', xml_declaration=True)
    return Response(output.getvalue(), mimetype='application/rss+xml')

@app.route("/categories/<slug>/feed.xml")
def category_rss_feed(slug):
    """Generate an RSS feed for a specific category"""
    categories = get_categories()
    if slug not in categories:
        return "Category not found", 404
    
    events = get_events()
    filtered_events = [e for e in events if slug in e.get('categories', [])]
    
    category = categories[slug]
    feed_title = f"{category['name']} Events - {SITE_NAME}"
    feed_description = f"Upcoming {category['name']} technology events in and around Washington, DC"
    feed_link = f"{BASE_URL}/categories/{slug}/"
    
    return generate_rss_feed_from_events(filtered_events, feed_title, feed_description, feed_link)

@app.route("/locations/<state>/feed.xml")
def location_rss_feed(state):
    """Generate an RSS feed for a specific location"""
    state = state.upper()
    if state not in ['DC', 'VA', 'MD']:
        return "Region not found", 404
    
    events = get_events()
    filtered_events = filter_events_by_location(events, state=state)
    
    region_name = get_region_name(state)
    feed_title = f"{region_name} Events - {SITE_NAME}"
    feed_description = f"Upcoming technology events in {region_name}"
    feed_link = f"{BASE_URL}/locations/{state.lower()}/"
    
    return generate_rss_feed_from_events(filtered_events, feed_title, feed_description, feed_link)

@app.route("/events-feed.xml")
def rss_feed():
    """
    Generate RSS feed of recently added events.
    """
    recent_events = db_utils.get_recently_added(limit=50)
    feed_title = f"{SITE_NAME} - New Events"
    feed_description = "Recently added events"
    feed_link = BASE_URL
    return generate_rss_feed_from_events(recent_events, feed_title, feed_description, feed_link)

def get_recently_added_events(limit=5):
    """
    Get the N most recently added events from DynamoDB.
    """
    return db_utils.get_recently_added(limit)

@app.route('/just-added/')
def just_added():
    """
    Display the three most recent days with newly added events.
    """
    recent_events = db_utils.get_recently_added(limit=100)
    
    if not recent_events:
        return render_template('just_added.html',
                             days_with_events=[],
                             error_message="No recent events found")

    events_by_date = {}
    for event in recent_events:
        createdAt = event.get('createdAt')
        if not createdAt:
            continue
        
        try:
            created_dt = datetime.fromisoformat(createdAt.replace('Z', '+00:00'))
            created_local = created_dt.astimezone(local_tz)
            date_key = created_local.date()
            if date_key not in events_by_date:
                events_by_date[date_key] = []
            event['date_added_display'] = created_local.strftime('%b %d, %I:%M %p')
            events_by_date[date_key].append(event)
        except (ValueError, AttributeError):
            continue
            
    days_with_events = []
    for date_obj, day_events in sorted(events_by_date.items(), key=lambda x: x[0], reverse=True):
        if len(day_events) > 100:
            continue
        
        anchor = f"{date_obj.month}-{date_obj.day}-{date_obj.year}"
        date_display = f"{date_obj.strftime('%A, %B')} {date_obj.day}, {date_obj.year}"
            
        days_with_events.append({
            'date': date_obj,
            'date_display': date_display,
            'anchor': anchor,
            'count': len(day_events),
            'events': sorted(day_events, key=lambda x: x.get('createdAt', ''), reverse=True)
        })
        
        if len(days_with_events) >= 3:
            break
            
    return render_template('just_added.html', days_with_events=days_with_events)


@app.route('/404.html')
def not_found_page():
    """Serve the 404 error page"""
    return render_template('404.html')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
