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

if __name__ == '__main__':
    freezer.freeze()
    print(f"Static site generated in {app.config['FREEZER_DESTINATION']}")