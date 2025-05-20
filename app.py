from flask import Flask, render_template, request
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
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading YAML from {file_path}: {str(e)}")
        return []

def get_events(month_name=None, year=None):
    """
    Get events from the appropriate YAML file
    
    Args:
        month_name: The name of the month (lowercase) to get events for
                   If None, returns upcoming events
        year: The year for the events (required if month_name is provided)
    
    Returns:
        A list of events
    """
    if month_name and year:
        file_path = os.path.join(DATA_DIR, f"{year}_{month_name.lower()}.yaml")
    elif month_name:
        # For backward compatibility, try to find any file with this month name
        # This should be removed once all files are migrated to the new format
        import glob
        pattern = os.path.join(DATA_DIR, f"*_{month_name.lower()}.yaml")
        files = glob.glob(pattern)
        if files:
            file_path = files[0]  # Use the first matching file
        else:
            return []
    else:
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
                # Only include active groups
                if group.get('active', True):
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
        
        # Parse the date
        event_date = datetime.strptime(day_key, '%Y-%m-%d').date()
        short_date = event_date.strftime('%a %-m/%-d')  # Format as "Mon 5/5"
        
        if day_key not in events_by_day:
            events_by_day[day_key] = {
                'date': day_key,
                'short_date': short_date,
                'time_slots': {}
            }
        
        # Format and group by time
        time_key = 'TBD'
        if 'time' in event:
            try:
                time_obj = datetime.strptime(event['time'], '%H:%M').time()
                event['time'] = time_obj.strftime('%-I:%M %p').lower()  # Format as "1:30 pm"
                time_key = event['time']
            except:
                pass
        
        if time_key not in events_by_day[day_key]['time_slots']:
            events_by_day[day_key]['time_slots'][time_key] = []
        
        events_by_day[day_key]['time_slots'][time_key].append(event)
    
    # Convert the dictionary to a sorted list of days
    sorted_days = sorted(events_by_day.keys())
    days_data = []
    
    for day in sorted_days:
        day_data = events_by_day[day]
        # Sort events within each time slot
        time_slots = []
        sorted_times = sorted(day_data['time_slots'].keys())
        
        # Move 'TBD' to the end if it exists
        if 'TBD' in sorted_times:
            sorted_times.remove('TBD')
            sorted_times.append('TBD')
        
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
    Get all future months with events, excluding current and next month
    
    Returns:
        A dictionary with years as keys and lists of month data as values
    """
    import glob
    import re
    
    # Get current date
    today = datetime.now(local_tz).date()
    current_month = today.month
    current_year = today.year
    
    # Calculate next month
    if current_month == 12:
        next_month = 1
        next_month_year = current_year + 1
    else:
        next_month = current_month + 1
        next_month_year = current_year
    
    # Find all month files
    pattern = os.path.join(DATA_DIR, "*.yaml")
    files = glob.glob(pattern)
    
    # Dictionary to store months by year
    years_months = {}
    
    # Regular expression to extract year and month from filenames
    file_pattern = re.compile(r'(\d{4})_([a-z]+)\.yaml')
    
    for file_path in files:
        # Skip the upcoming.yaml file
        if os.path.basename(file_path) == 'upcoming.yaml':
            continue
            
        # Extract year and month from filename
        match = file_pattern.search(os.path.basename(file_path))
        if match:
            year_str, month_name = match.groups()
            year = int(year_str)
            
            # Convert month name to number
            month_names = {month.lower(): i for i, month in enumerate(calendar.month_name) if i > 0}
            if month_name not in month_names:
                continue
                
            month_num = month_names[month_name]
            
            if (year < current_year or 
                (year == current_year and month_num < current_month)):
                continue
                
            # Count events in the file
            events = load_yaml_data(file_path) or []
            event_count = len(events)
            
            # Skip if no events
            if event_count == 0:
                continue
                
            # Add to the dictionary
            if year not in years_months:
                years_months[year] = []
                
            years_months[year].append({
                'name': month_name.capitalize(),
                'number': month_num,
                'count': event_count,
                'year': year
            })
    
    # Sort months within each year
    for year in years_months:
        years_months[year].sort(key=lambda x: x['number'])
    
    # Sort years
    sorted_years = sorted(years_months.keys())
    result = {year: years_months[year] for year in sorted_years}
    
    return result

def get_next_week_and_month_dates(events):
    """
    Get the dates for next week and next month, finding the nearest event dates
    
    Args:
        events: List of event dictionaries
    
    Returns:
        A tuple of (next_week_date, next_month_date)
    """
    today = datetime.now(local_tz).date()
    
    # Next week target (7 days from today)
    next_week_target = today + timedelta(days=7)
    # Next month target (first day of next month)
    if today.month == 12:
        next_month_target = date(today.year + 1, 1, 1)
    else:
        next_month_target = date(today.year, today.month + 1, 1)
    
    # Convert events dates to date objects
    event_dates = []
    for event in events:
        try:
            event_date = datetime.strptime(event['date'], '%Y-%m-%d').date()
            if event_date >= today:  # Only consider future events
                event_dates.append(event_date)
        except:
            continue
    
    if not event_dates:
        # If no events, return the target dates
        return (next_week_target.strftime('%Y-%m-%d'), 
                next_month_target.strftime('%Y-%m-%d'))
    
    # Sort dates
    event_dates.sort()
    
    # Find nearest future date to next week target
    next_week_date = min(event_dates, 
                        key=lambda d: abs((d - next_week_target).days))
    
    # Find nearest future date to next month target
    next_month_date = min(event_dates, 
                         key=lambda d: abs((d - next_month_target).days))
    
    return (next_week_date.strftime('%Y-%m-%d'), 
            next_month_date.strftime('%Y-%m-%d'))

@app.route("/")
def homepage():
    # Get upcoming events
    events = get_events()
    days = prepare_events_by_day(events)
    
    # Get future months with events
    future_months = get_future_months_with_events()
    
    # Get next week and month dates
    next_week_date, next_month_date = get_next_week_and_month_dates(events)
    
    return render_template('homepage.html', 
                          days=days, 
                          future_months=future_months,
                          next_week_date=next_week_date,
                          next_month_date=next_month_date,
                          site_name=SITE_NAME)

@app.route("/<int:year>/<int:month>/")
def month_view(year, month):
    # Get the month name
    month_name = calendar.month_name[month].lower()
    
    # Get events for the month
    events = get_events(month_name, year)
    days = prepare_events_by_day(events)
    
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
                          year=year, 
                          month=month,
                          month_name=calendar.month_name[month],
                          prev_month=prev_month,
                          prev_year=prev_year,
                          next_month=next_month,
                          next_year=next_year,
                          site_name=SITE_NAME)

@app.route("/groups/")
def approved_groups_list():
    # Get all groups
    groups = get_approved_groups()
    
    return render_template('approved_groups_list.html', 
                          groups=groups, 
                          next_key=None,
                          has_next=False,
                          site_name=SITE_NAME)

@app.route("/add-events/")
def add_events_page():
    return render_template('add_events.html', site_name=SITE_NAME)



if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)