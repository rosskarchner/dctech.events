#!/usr/bin/env python3
from flask_frozen import Freezer
from app import app

# Configure Freezer to ignore API routes
app.config['FREEZER_IGNORE_ENDPOINTS'] = [
    'events_routes.event_suggest_form',
    'events_routes.submit_event',
    'events_routes.events_manage',
    'events_routes.edit_event_form',
    'events_routes.edit_event',
    'events_routes.set_event_pending',
    'events_routes.events_review',
    'events_routes.approve_event_route',
    'events_routes.delete_event_route',
    'groups_routes.groups_manage',
    'groups_routes.groups_import_form',
    'groups_routes.groups_import',
    'groups_routes.approve_group_route',
    'groups_routes.delete_group_route',
    'groups_routes.set_group_pending_route',
    'groups_routes.group_suggest_form',
    'groups_routes.submit_group',
    'groups_routes.edit_group_form',
    'groups_routes.export_groups_csv',
    'groups_routes.edit_group'
]

freezer = Freezer(app)

if __name__ == '__main__':
    freezer.freeze()