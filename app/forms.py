from flask_wtf import FlaskForm
from wtforms import StringField, URLField, DateField, SelectField, FileField
from wtforms.validators import DataRequired, URL, Optional, Length

class EventForm(FlaskForm):
    class Meta:
        csrf = False  # Disable CSRF for cross-domain form submission
    
    title = StringField('Event Title', validators=[DataRequired(), Length(min=3, max=100)])
    event_date = DateField('Event Date', format='%Y-%m-%d', validators=[DataRequired()])
    event_hour = SelectField('Hour', choices=[(str(i), str(i)) for i in range(1, 13)], default='6')
    event_minute = SelectField('Minute', choices=[('00', '00'), ('15', '15'), ('30', '30'), ('45', '45')], default='00')
    event_ampm = SelectField('AM/PM', choices=[('AM', 'AM'), ('PM', 'PM')], default='PM')
    location = StringField('Location', validators=[Optional(), Length(max=200)])
    url = URLField('Event URL', validators=[DataRequired(), URL()])

class GroupForm(FlaskForm):
    class Meta:
        csrf = False  # Disable CSRF for cross-domain form submission
    
    name = StringField('Group Name', validators=[DataRequired(), Length(min=3, max=100)])
    website = URLField('Group Website', validators=[DataRequired(), URL()])
    ical = URLField('iCal URL', validators=[DataRequired(), URL()])
    fallback_url = URLField('Fallback URL', validators=[Optional(), URL()])

class GroupCSVImportForm(FlaskForm):
    class Meta:
        csrf = False  # Disable CSRF for cross-domain form submission
    
    csv_file = FileField('CSV File', validators=[DataRequired()])
