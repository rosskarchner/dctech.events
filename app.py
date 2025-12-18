from flask import Flask, render_template, request, Response
from datetime import date, datetime, timedelta
import os
import yaml
import pytz
import calendar
import json
from pathlib import Path
from location_utils import extract_location_info, get_region_name
from PIL import Image, ImageDraw, ImageFont, __version__ as PIL_VERSION
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
TAGLINE = config.get('tagline', 'Technology conferences and meetups in and around Washington, DC')
BASE_URL = config.get('base_url', 'https://dctech.events')
ADD_EVENTS_LINK = config.get('add_events_link', 'https://add.dctech.events')
NEWSLETTER_SIGNUP_LINK = config.get('newsletter_signup_link', 'https://newsletter.dctech.events')

# Constants - data paths
DATA_DIR = '_data'
GROUPS_DIR = '_groups'
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
        'sponsors': load_sponsors()
    }

    return context

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
                return (-1, 0)  # Put TBD (events without time) at the beginning
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
    Generate a calendar image for a week showing events as a list.

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

    # Colors - light, professional theme
    bg_color = '#f8f9fa'
    text_color = '#1f2937'
    brand_color = '#2563eb'
    day_color = '#374151'
    event_color = '#4b5563'
    url_color = '#6b7280'
    accent_bg = '#e0e7ff'

    # Create image
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Get bundled font paths
    font_dir = os.path.join(os.path.dirname(__file__), 'fonts')
    dejavu_bold = os.path.join(font_dir, 'DejaVuSans-Bold.ttf')
    dejavu_regular = os.path.join(font_dir, 'DejaVuSans.ttf')
    noto_emoji = os.path.join(font_dir, 'NotoColorEmoji.ttf')

    # Fallback to system fonts if bundled fonts not found
    if not os.path.exists(dejavu_bold):
        dejavu_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    if not os.path.exists(dejavu_regular):
        dejavu_regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if not os.path.exists(noto_emoji):
        noto_emoji = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

    # Try to load fonts, fall back to default if not available
    try:
        title_font = ImageFont.truetype(dejavu_bold, 50)
        url_font = ImageFont.truetype(dejavu_regular, 20)
        day_font = ImageFont.truetype(dejavu_bold, 22)
        event_font = ImageFont.truetype(dejavu_regular, 20)
        small_font = ImageFont.truetype(dejavu_regular, 17)
    except:
        title_font = ImageFont.load_default()
        url_font = ImageFont.load_default()
        day_font = ImageFont.load_default()
        event_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Try to load emoji font for emoji support
    emoji_font = None
    emoji_font_event = None
    emoji_font_day = None
    try:
        emoji_font = ImageFont.truetype(noto_emoji, 50)
        emoji_font_event = ImageFont.truetype(noto_emoji, 20)
        emoji_font_day = ImageFont.truetype(noto_emoji, 22)
    except:
        pass

    # Helper to draw text with emoji support
    def draw_text_with_emoji(xy, text, fill, font, emoji_font_override=None):
        """Draw text with emoji support using bundled Noto Color Emoji font"""
        import re

        # Check if text contains emoji
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)

        has_emoji = bool(emoji_pattern.search(text))

        # PIL 10+ supports embedded_color for color emoji fonts
        if has_emoji and emoji_font_override:
            try:
                # Use emoji font with embedded_color for text containing emoji
                # Note: This renders the entire text with the emoji font
                draw.text(xy, text, font=emoji_font_override, fill=fill, embedded_color=True)
                return
            except:
                # If embedded_color fails, fallthrough
                pass

        # Use regular font (emoji may not render but text will)
        draw.text(xy, text, fill=fill, font=font)

    # Helper function to get ordinal suffix
    def get_ordinal_suffix(day):
        if 10 <= day % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
        return suffix

    # Draw header background bar
    header_height = 90
    draw.rectangle([0, 0, width, header_height], fill=accent_bg)

    # Draw combined title
    day_num = int(week_start.strftime('%-d'))
    ordinal_suffix = get_ordinal_suffix(day_num)
    title_text = f"DC Tech Events for the week of {week_start.strftime('%B %-d')}{ordinal_suffix}, {week_start.strftime('%Y')}"
    draw_text_with_emoji((30, 15), title_text, fill=brand_color, font=title_font, emoji_font_override=emoji_font)

    # Draw URL below in smaller text
    url_text = "dctech.events"
    draw_text_with_emoji((30, 68), url_text, fill=url_color, font=url_font)

    # Prepare events by day
    days_data = prepare_events_by_day(events)
    events_by_date = {day['date']: day for day in days_data}

    # Calculate how many events we have and determine layout
    total_events = sum(
        len([e for ts in day['time_slots'] for e in ts['events']])
        for day in days_data if day.get('has_events', False)
    )
    days_with_events_count = sum(1 for day in days_data if day.get('has_events', False))

    # Available vertical space
    available_height = height - header_height - 40  # 40px margin at bottom

    # Estimate space needed per event and day header
    base_day_header_space = 32
    base_event_space = 28
    base_day_spacing = 10

    # Calculate if we need two columns
    estimated_space_needed = (days_with_events_count * (base_day_header_space + base_day_spacing)) + (total_events * base_event_space)
    use_two_columns = estimated_space_needed > available_height

    # Adjust spacing and max events based on layout
    if use_two_columns:
        max_events_per_day = 4
        line_height = 26
        day_spacing = 6
    else:
        # Calculate dynamic spacing for single column
        if estimated_space_needed > available_height:
            # Need to compress
            scale_factor = available_height / estimated_space_needed
            line_height = max(22, int(base_event_space * scale_factor))
            day_spacing = max(4, int(base_day_spacing * scale_factor))
            max_events_per_day = 3
        else:
            line_height = 28
            day_spacing = 8
            max_events_per_day = 5

    # Layout configuration
    margin_left = 30
    margin_right = 30
    y_position = header_height + 20
    max_text_width = width - margin_left - margin_right

    if use_two_columns:
        column_width = (width - 3 * margin_left) // 2
        max_text_width = column_width

    # Helper function to truncate text
    def truncate_text(text, font, max_width):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        if text_width <= max_width:
            return text
        while len(text) > 0:
            test_text = text + '...'
            bbox = draw.textbbox((0, 0), test_text, font=font)
            if bbox[2] - bbox[0] <= max_width:
                return test_text
            text = text[:-1]
        return '...'

    # Draw events by day
    current_date = week_start
    days_with_events = 0

    # Two-column setup if needed
    if use_two_columns:
        left_column_x = 30
        right_column_x = 30 * 2 + column_width
        initial_y = y_position
        in_left_column = True

    for i in range(7):
        date_key = current_date.strftime('%Y-%m-%d')

        # Check if this day has events
        if date_key in events_by_date and events_by_date[date_key]['has_events']:
            days_with_events += 1

            # Check if we need to switch to right column or are out of space
            bottom_threshold = height - 50
            if y_position > bottom_threshold:
                if use_two_columns and in_left_column:
                    # Switch to right column
                    y_position = initial_y
                    margin_left = right_column_x
                    max_text_width = column_width
                    in_left_column = False
                else:
                    # Out of space - truncate remaining
                    if y_position < height - 30:
                        draw_text_with_emoji((margin_left, y_position), "...", fill=event_color, font=small_font)
                    break

            # Draw day header
            day_header = current_date.strftime('%a, %b %-d')
            draw_text_with_emoji((margin_left, y_position), day_header, fill=day_color, font=day_font, emoji_font_override=emoji_font_day)
            y_position += line_height + 2

            # Collect all events for this day
            all_events = []
            for time_slot in events_by_date[date_key]['time_slots']:
                for event in time_slot['events']:
                    all_events.append(event)

            # Draw events (limit to max_events_per_day)
            events_shown = 0
            for event in all_events:
                # Check if we have space for another event
                if y_position + line_height > bottom_threshold:
                    if events_shown < len(all_events):
                        remaining = len(all_events) - events_shown
                        if y_position < height - 30:
                            draw_text_with_emoji((margin_left + 15, y_position),
                                     f"+ {remaining} more",
                                     fill=event_color, font=small_font)
                    break

                if events_shown >= max_events_per_day:
                    remaining = len(all_events) - events_shown
                    draw_text_with_emoji((margin_left + 15, y_position),
                             f"+ {remaining} more",
                             fill=event_color, font=small_font)
                    y_position += line_height
                    break

                # Truncate long event titles
                event_title = truncate_text(event.get('title', 'Untitled'), event_font, max_text_width - 25)

                # Draw bullet and event
                draw_text_with_emoji((margin_left + 5, y_position), "•", fill=brand_color, font=event_font)
                draw_text_with_emoji((margin_left + 20, y_position), event_title, fill=text_color, font=event_font, emoji_font_override=emoji_font_event)
                y_position += line_height
                events_shown += 1

            # Add spacing after this day
            y_position += day_spacing

        current_date += timedelta(days=1)

    # If no events found, show message
    if days_with_events == 0:
        y_position = header_height + 100
        draw_text_with_emoji((margin_left, y_position), "No events scheduled this week",
                 fill=event_color, font=event_font)
        y_position += line_height + 10
        draw_text_with_emoji((margin_left, y_position), "Check back soon or add your event!",
                 fill=event_color, font=url_font)

    return img

@app.route("/")
def homepage():
    # Get upcoming events
    events = get_events()
    days = prepare_events_by_day(events, add_week_links=True)

    # Get base URL from config or use a default
    base_url = BASE_URL

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

# Image generation temporarily disabled
# @app.route("/week/<week_id>/image.png")
# def week_image(week_id):
#     """Generate and serve the calendar image for a specific week"""
#     try:
#         year, week_num = parse_week_identifier(week_id)
#         week_start, week_end = get_iso_week_dates(year, week_num)
#     except:
#         return "Invalid week identifier", 404
#
#     # Get all events and filter by week
#     events = get_events()
#     week_events = filter_events_by_week(events, week_start, week_end)
#
#     # Generate the image
#     img = generate_week_calendar_image(week_start, week_end, week_events)
#
#     # Convert to bytes
#     img_io = io.BytesIO()
#     img.save(img_io, 'PNG')
#     img_io.seek(0)
#
#     return Response(img_io.getvalue(), mimetype='image/png')

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

@app.route("/submit/")
def submit():
    """Event submission page with GitHub OAuth"""
    # Get OAuth configuration from environment or config
    github_client_id = os.environ.get('GITHUB_CLIENT_ID', config.get('github_client_id', ''))
    oauth_callback_endpoint = os.environ.get('OAUTH_CALLBACK_ENDPOINT',
                                            config.get('oauth_callback_endpoint', ''))

    return render_template('submit.html',
                          github_client_id=github_client_id,
                          oauth_callback_endpoint=oauth_callback_endpoint)

@app.route("/submit-group/")
def submit_group():
    """Group submission page with GitHub OAuth"""
    # Get OAuth configuration from environment or config
    github_client_id = os.environ.get('GITHUB_CLIENT_ID', config.get('github_client_id', ''))
    oauth_callback_endpoint = os.environ.get('OAUTH_CALLBACK_ENDPOINT',
                                            config.get('oauth_callback_endpoint', ''))

    return render_template('submit-group.html',
                          github_client_id=github_client_id,
                          oauth_callback_endpoint=oauth_callback_endpoint)

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

    return Response('\n'.join(xml), mimetype='text/xml')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)