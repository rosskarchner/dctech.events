from flask import Flask, render_template, request, Response
from datetime import date, datetime, timedelta
import os
import yaml
import pytz
import calendar
from pathlib import Path

# Load configuration
CONFIG_FILE = 'config.yaml'
config = {}
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r') as f:
        config = yaml.safe_load(f)

# Define timezone from config
timezone_name = config.get('timezone', 'US/Eastern')
local_tz = pytz.timezone(timezone_name)

# Get site name from config
SITE_NAME = config.get('site_name', 'DC Tech Events')

# Constants
DATA_DIR = '_data'
GROUPS_DIR = '_groups'

app = Flask(__name__, template_folder='templates')

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

def prepare_events_by_day(events):
    """
    Organize events by day and time
    
    Args:
        events: List of event dictionaries
    
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
                events_by_day[day_key] = {
                    'date': day_key,
                    'short_date': short_date,
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
            # For display, use the formatted time
            event_copy['time'] = formatted_time
            
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

@app.route("/")
def homepage():
    # Get upcoming events
    events = get_events()
    days = prepare_events_by_day(events)
    

    # Get stats
    stats = get_stats()
    print(days)
    return render_template('homepage.html', 
                          days=days, 
                          site_name=SITE_NAME,
                          stats=stats)

# Month view route removed - all events are now in upcoming.yaml

@app.route("/groups/")
def approved_groups_list():
    # Get all groups
    groups = get_approved_groups()
    
    return render_template('approved_groups_list.html', 
                          groups=groups, 
                          next_key=None,
                          has_next=False,
                          site_name=SITE_NAME)

@app.route("/newsletter.html")
def newsletter_html():
    # Get upcoming events
    events = get_events()
    days = prepare_events_by_day(events)
    
    # Get stats
    stats = get_stats()
    
    return render_template('newsletter.html',
                          days=days,
                          site_name=SITE_NAME,
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
                             site_name=SITE_NAME,
                             stats=stats)
    return response, 200, {'Content-Type': 'text/plain; charset=utf-8'}

@app.route("/sitemap.xml")
def sitemap():
    """Generate an XML sitemap of the site's main pages"""
    # Get base URL from config or use a default
    base_url = config.get('base_url', 'https://dctech.events')
    
    # Create list of URLs with last modified dates
    urls = [
        {'loc': f"{base_url}/", 'lastmod': datetime.now().strftime('%Y-%m-%d')},
        {'loc': f"{base_url}/groups/", 'lastmod': datetime.now().strftime('%Y-%m-%d')},
    ]
    
    # Generate XML sitemap
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    for url in urls:
        xml.append('  <url>')
        xml.append(f'    <loc>{url["loc"]}</loc>')
        xml.append(f'    <lastmod>{url["lastmod"]}</lastmod>')
        xml.append('    <changefreq>daily</changefreq>')
        xml.append('  </url>')
    
    xml.append('</urlset>')
    
    return Response('\n'.join(xml), mimetype='application/xml')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)