#!/usr/bin/env python3
from flask_frozen import Freezer
from app import app, local_tz
import os
import calendar
from datetime import datetime, timedelta

# Configure Freezer
app.config['FREEZER_DESTINATION'] = 'build'
app.config['FREEZER_RELATIVE_URLS'] = True

freezer = Freezer(app)

@freezer.register_generator
def month_view():
    # Generate URLs for the next 12 months
    now = datetime.now(local_tz)
    for i in range(12):
        month = ((now.month - 1 + i) % 12) + 1
        year = now.year + ((now.month - 1 + i) // 12)
        yield {'year': year, 'month': month}

if __name__ == '__main__':
    freezer.freeze()
    print(f"Static site generated in {app.config['FREEZER_DESTINATION']}")