from flask import Flask, render_template, request, Response
from datetime import date, datetime, timedelta
import os
import yaml
import pytz
import calendar
from pathlib import Path
from location_utils import extract_location_info, get_region_name
from PIL import Image, ImageDraw, ImageFont
import io

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
TAGLINE = config.get('tagline', 'Technology events in the area')
BASE_URL = config.get('base_url', 'https://dctech.events')
ADD_EVENTS_LINK = config.get('add_events_link', 'https://add.dctech.events')
NEWSLETTER_SIGNUP_LINK = config.get('newsletter_signup_link', 'https://newsletter.dctech.events')

# Constants
DATA_DIR = '_data'
GROUPS_DIR = '_groups'

app = Flask(__name__, template_folder='templates')

@app.context_processor
def inject_config():
    return {
        'site_name': SITE_NAME,
        'tagline': TAGLINE,
        'base_url': BASE_URL,
        'add_events_link': ADD_EVENTS_LINK,
        'newsletter_signup_link': NEWSLETTER_SIGNUP_LINK
    }

def load_yaml_data(file_path):
    """Load data from a YAML file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading YAML from {file_path}: {str(e)}")
        return []

def get_events():
    """
    Get events from the upcoming.yaml file
    
    Returns:
        A list of events
    """
    file_path = os.path.join(DATA_DIR, 'upcoming.yaml')
    
    if not os.path.exists(file_path):
        return []
    
    return load_yaml_data(file_path) or []

def get_approved_groups():
    """
    Get all groups from the _groups directory
    
    Returns:
        A list of group dictionaries
    """
    groups = []
    for file_path in Path(GROUPS_DIR).glob('*.yaml'):
        try:
            with open(file_path, 'r') as f:
                group = yaml.safe_load(f)
                # Add the group ID (filename without extension)
                group['id'] = file_path.stem

                groups.append(group)
        except Exception as e:
            print(f"Error loading group from {file_path}: {str(e)}")
    
    # Sort groups by name
    groups.sort(key=lambda x: x.get('name', '').lower())
    
    return groups

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
            except:
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

            # Format time once for all days
            time_key = 'TBD'
            formatted_time = 'TBD'
            original_time = event.get('time', '')

            # Only try to parse time if it exists and hasn't been formatted yet
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
                    # If time parsing fails, keep TBD
                    pass

            # Store both the original and formatted time
            event['original_time'] = original_time
            event['formatted_time'] = formatted_time

            # Create a copy of the event for this day
            event_copy = event.copy()
            # Store the machine-readable time (HH:MM format) for datetime attribute
            event_copy['time'] = time_key if time_key != 'TBD' else ''
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
            if time_str == 'TBD':
                return (24, 0)  # Put TBD at the end
            try:
                # Parse time like "1:30 pm" or "10:00 am"
                parts = time_str.split()
                time_part = parts[0]
                am_pm = parts[1] if len(parts) > 1 else 'am'

                hour, minute = map(int, time_part.split(':'))

                # Convert to 24-hour format for sorting
                if am_pm.lower() == 'pm' and hour < 12:
                    hour += 12
                elif am_pm.lower() == 'am' and hour == 12:
                    hour = 0

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

def get_future_months_with_events():
    """
    This function is no longer used as we don't break down events by month anymore.
    Returns an empty dictionary.
    
    Returns:
        An empty dictionary
    """
    return {}


def get_stats():
    """
    Load statistics from stats.yaml
    
    Returns:
        Dictionary containing stats, or empty dict if file doesn't exist
    """
    stats_file = os.path.join(DATA_DIR, 'stats.yaml')
    if not os.path.exists(stats_file):
        return {}
    return load_yaml_data(stats_file) or {}

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
                except:
                    pass

            # Include event if it overlaps with the week
            if (event_date <= week_end and end_date >= week_start):
                filtered.append(event)
        except:
            continue

    return filtered

def get_upcoming_weeks(num_weeks=12):
    """
    Get a list of upcoming ISO week identifiers.

    Args:
        num_weeks: Number of weeks to generate (default 12)

    Returns:
        List of week identifier strings
    """
    weeks = []
    current_date = date.today()

    for i in range(num_weeks):
        week_date = current_date + timedelta(weeks=i)
        week_id = get_week_identifier(week_date)
        if week_id not in weeks:  # Avoid duplicates
            weeks.append(week_id)

    return weeks

def generate_week_calendar_image(week_start, week_end, events):
    """
    Generate a calendar image for a week showing events.

    Args:
        week_start: Start date of the week (Monday)
        week_end: End date of the week (Sunday)
        events: List of events for the week

    Returns:
        PIL Image object
    """
    # Image dimensions
    width = 1200
    height = 630  # Standard OG image size

    # Colors
    bg_color = '#1a1a1a'
    text_color = '#ffffff'
    header_color = '#4a9eff'
    day_bg_color = '#2a2a2a'
    event_color = '#3a3a3a'

    # Create image
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Try to load fonts, fall back to default if not available
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        day_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        event_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        count_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
    except:
        title_font = ImageFont.load_default()
        day_font = ImageFont.load_default()
        event_font = ImageFont.load_default()
        count_font = ImageFont.load_default()

    # Draw title
    title = f"Week of {week_start.strftime('%B %-d, %Y')}"
    draw.text((50, 40), title, fill=header_color, font=title_font)

    # Prepare events by day
    days_data = prepare_events_by_day(events)
    events_by_date = {day['date']: day for day in days_data}

    # Draw calendar grid
    margin = 50
    top_offset = 120
    day_width = (width - 2 * margin) // 7
    day_height = height - top_offset - margin

    current_date = week_start
    for i in range(7):
        x = margin + i * day_width
        y = top_offset

        # Draw day box
        draw.rectangle([x, y, x + day_width - 5, y + day_height],
                      fill=day_bg_color, outline=text_color)

        # Draw day name and date
        day_name = current_date.strftime('%a')
        day_num = current_date.strftime('%-d')
        day_text = f"{day_name}\n{day_num}"

        # Center the day text
        draw.text((x + day_width // 2, y + 15), day_text,
                 fill=text_color, font=day_font, anchor="mt")

        # Count events for this day
        date_key = current_date.strftime('%Y-%m-%d')
        event_count = 0
        if date_key in events_by_date:
            for time_slot in events_by_date[date_key]['time_slots']:
                event_count += len(time_slot['events'])

        # Draw event count if there are events
        if event_count > 0:
            count_text = str(event_count)
            draw.text((x + day_width // 2, y + day_height // 2), count_text,
                     fill=header_color, font=count_font, anchor="mm")

            event_label = "event" if event_count == 1 else "events"
            draw.text((x + day_width // 2, y + day_height // 2 + 40), event_label,
                     fill=text_color, font=event_font, anchor="mm")

        current_date += timedelta(days=1)

    # Add site branding
    site_text = SITE_NAME
    draw.text((width - margin, height - 30), site_text,
             fill=text_color, font=event_font, anchor="rm")

    return img

@app.route("/")
def homepage():
    # Get upcoming events
    events = get_events()
    days = prepare_events_by_day(events, add_week_links=True)

    # Get base URL from config or use a default
    base_url = config.get('base_url', 'https://dctech.events')

    # Get stats
    stats = get_stats()
    return render_template('homepage.html',
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

    # Calculate previous and next week identifiers
    prev_week_date = week_start - timedelta(days=7)
    next_week_date = week_start + timedelta(days=7)
    prev_week = get_week_identifier(prev_week_date)
    next_week = get_week_identifier(next_week_date)

    # Format week start for display
    week_start_formatted = week_start.strftime('%B %-d, %Y')

    # Get stats
    stats = {'upcoming_events': len(week_events)}

    # Get base URL
    base_url = config.get('base_url', 'https://dctech.events')

    # Generate the OG image URL
    og_image_url = f"{base_url}/week/{week_id}/image.png"

    return render_template('week_page.html',
                          days=days,
                          stats=stats,
                          week_id=week_id,
                          week_start=week_start,
                          week_end=week_end,
                          week_start_formatted=week_start_formatted,
                          prev_week=prev_week,
                          next_week=next_week,
                          og_image_url=og_image_url,
                          base_url=base_url)

@app.route("/week/<week_id>/image.png")
def week_image(week_id):
    """Generate and serve the calendar image for a specific week"""
    try:
        year, week_num = parse_week_identifier(week_id)
        week_start, week_end = get_iso_week_dates(year, week_num)
    except:
        return "Invalid week identifier", 404

    # Get all events and filter by week
    events = get_events()
    week_events = filter_events_by_week(events, week_start, week_end)

    # Generate the image
    img = generate_week_calendar_image(week_start, week_end, week_events)

    # Convert to bytes
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)

    return Response(img_io.getvalue(), mimetype='image/png')

# Month view route removed - all events are now in upcoming.yaml

@app.route("/locations/")
def locations_index():
    """Show available locations with event counts"""
    events = get_events()
    
    # Count events by location
    location_stats = {}
    cities = set()
    
    for event in events:
        city, state = extract_location_info(event.get('location', ''))
        if state in ['DC', 'VA', 'MD']:
            # Add to region count
            region = get_region_name(state)
            location_stats[region] = location_stats.get(region, 0) + 1
            
            # Add to city count (skip Washington, DC since it's same as DC region)
            if city and not (city == 'Washington' and state == 'DC'):
                city_key = f"{city}, {state}"
                cities.add((city, state))
    
    # Get city counts
    city_stats = {}
    for city, state in cities:
        city_events = filter_events_by_location(events, city=city, state=state)
        if len(city_events) > 0:
            city_name = city if state != 'DC' else 'Washington'
            city_stats[f"{city_name}, {state}"] = len(city_events)
    
    return render_template('locations_index.html',
                          location_stats=location_stats,
                          city_stats=city_stats)

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
    days = prepare_events_by_day(events)
    
    # Get stats
    stats = get_stats()
    
    return render_template('newsletter.html',
                          days=days,
                          stats=stats)

@app.route("/newsletter.txt")
def newsletter_text():
    # Get upcoming events
    events = get_events()
    days = prepare_events_by_day(events)
    
    # Get stats
    stats = get_stats()
    
    response = render_template('newsletter.txt',
                             days=days,
                             stats=stats)
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

@app.route("/locations/<state>/<city>/")
def city_page(state, city):
    """Show events for a specific city"""
    state = state.upper()
    if state not in ['DC', 'VA', 'MD']:
        return "Region not found", 404
    
    events = get_events()
    city_name = city.replace('-', ' ').title()
    filtered_events = filter_events_by_location(events, city=city_name, state=state)
    days = prepare_events_by_day(filtered_events)
    if state == 'DC':
        city_name = 'Washington DC'
    
    stats = {'upcoming_events': len(filtered_events)}
    
    return render_template('location_page.html',
                          days=days,
                          stats=stats,
                          location_name=f"{city_name}, {state}",
                          location_type='city')

@app.route("/sitemap.xml")
def sitemap():
    """Generate an XML sitemap of the site's main pages"""
    # Get base URL from config or use a default
    base_url = config.get('base_url', 'https://dctech.events')

    # Create list of URLs with last modified dates
    urls = [
        {'loc': f"{base_url}/", 'lastmod': datetime.now().strftime('%Y-%m-%d')},
        {'loc': f"{base_url}/groups/", 'lastmod': datetime.now().strftime('%Y-%m-%d')},
        {'loc': f"{base_url}/locations/", 'lastmod': datetime.now().strftime('%Y-%m-%d')},
        {'loc': f"{base_url}/locations/dc/", 'lastmod': datetime.now().strftime('%Y-%m-%d')},
        {'loc': f"{base_url}/locations/va/", 'lastmod': datetime.now().strftime('%Y-%m-%d')},
        {'loc': f"{base_url}/locations/md/", 'lastmod': datetime.now().strftime('%Y-%m-%d')},
    ]

    # Add upcoming week pages
    upcoming_weeks = get_upcoming_weeks(12)
    for week_id in upcoming_weeks:
        urls.append({
            'loc': f"{base_url}/week/{week_id}/",
            'lastmod': datetime.now().strftime('%Y-%m-%d'),
            'changefreq': 'daily'
        })

    # Generate XML sitemap
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

    return Response('\n'.join(xml), mimetype='application/xml')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)