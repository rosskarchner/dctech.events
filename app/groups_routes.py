from flask import Flask, jsonify, render_template, request, session, redirect, url_for, Response
from datetime import datetime
from forms import GroupForm, GroupCSVImportForm
import os
import uuid
from auth import login_required, group_required
from queries import (
    get_approved_groups, get_pending_groups, get_group_by_id, 
    approve_group, delete_group, set_group_pending, update_group, 
    import_groups_from_csv, export_groups_to_csv, get_site_slug
)

def register_groups_routes(app, groups_table):
    """Register all group-related routes with the Flask app"""
    
    def save_group_to_db(group_data):
        """Save group data to DynamoDB"""
        try:
            # Get SITEURL from environment or use default
            site_url = os.environ.get('SITEURL', 'http://localhost:5000')
            # Remove trailing slash if present
            if site_url.endswith('/'):
                site_url = site_url[:-1]
            # Create a site slug for the ID prefix
            site_slug = site_url.replace('http://', '').replace('https://', '').replace(':', '_').replace('/', '_')
            
            # Generate a unique ID with site prefix
            unique_id = f"{site_slug}!{str(uuid.uuid4())}"
            
            # Create the DynamoDB item
            item = {
                'id': unique_id,
                'name': group_data['name'],
                'website': group_data['website'],
                'ical': group_data.get('ical', ''),
                'fallback_url': group_data.get('fallback_url', ''),
                'approval_status': f"{site_slug}!PENDING",  # Namespaced approval status
                'active': True,
                'lastUpdated': datetime.now().isoformat(),
                'submissionDate': datetime.now().isoformat()
            }
            
            # Save to DynamoDB
            groups_table.put_item(Item=item)
            return True, item['id']
        except Exception as e:
            print(f"Error saving group to database: {str(e)}")
            return False, str(e)
    
    def _process_group_action(group_id, approval_state=None):
        """
        Common logic for processing group actions (approve, set pending, delete)
        
        Args:
            group_id: The ID of the group
            approval_state: The new approval state to set (APPROVED or PENDING), or None for delete
            
        Returns:
            Flask response with rendered template
        """
        api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
        
        # Perform the requested action - no longer adding site slug here
        # The queries.py functions will handle adding the site slug if needed
        if approval_state is None:
            # Delete the group
            success, message = delete_group(group_id)
        elif approval_state == "APPROVED":
            # Approve the group
            success, message = approve_group(group_id)
        elif approval_state == "PENDING":
            # Set the group to pending
            success, message = set_group_pending(group_id)
        else:
            success = False
            message = f"Invalid approval state: {approval_state}"
        
        # Get all pending and approved groups
        pending_groups, _ = get_pending_groups(limit=100)
        approved_groups, _ = get_approved_groups(limit=100)
        
        # Combine groups for display
        groups = pending_groups + approved_groups
        
        if success:
            return render_template('groups_manage.html', 
                                  groups=groups, 
                                  api_base_url=api_base_url, 
                                  message=message, 
                                  message_type="success")
        else:
            return render_template('groups_manage.html', 
                                  groups=groups, 
                                  api_base_url=api_base_url, 
                                  message=f"Error: {message}", 
                                  message_type="error")
    
    @app.route('/api/groups/manage', methods=['GET'])
    @login_required
    @group_required('localhost-moderators')
    def groups_manage():
        """Serve the group management page for HTMX inclusion"""
        # Get the base URL from environment or use default
        api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
        
        # Get all pending and approved groups (pagination is handled automatically in the query functions)
        pending_groups, _ = get_pending_groups(limit=100)
        approved_groups, _ = get_approved_groups(limit=100)
        
        # Combine groups for display
        groups = pending_groups + approved_groups
        
        return render_template('groups_manage.html', 
                              groups=groups, 
                              api_base_url=api_base_url)
    
    @app.route('/api/groups/import-form', methods=['GET'])
    @login_required
    @group_required('localhost-moderators')
    def groups_import_form():
        """Serve the group import form for HTMX inclusion"""
        # Get the base URL from environment or use default
        api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
        
        # Create form
        form = GroupCSVImportForm()
        
        return render_template('group_import_form.html', form=form, api_base_url=api_base_url)
    
    @app.route('/api/groups/import', methods=['POST'])
    @login_required
    @group_required('localhost-moderators')
    def groups_import():
        """Handle group import from CSV"""
        # Get the base URL from environment or use default
        api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
        
        # Check if file was uploaded
        if 'csv_file' not in request.files:
            return render_template('group_import_result.html', 
                                  success=False, 
                                  message="No file uploaded", 
                                  api_base_url=api_base_url)
        
        file = request.files['csv_file']
        
        # Check if file is empty
        if file.filename == '':
            return render_template('group_import_result.html', 
                                  success=False, 
                                  message="No file selected", 
                                  api_base_url=api_base_url)
        
        # Check if file is a CSV
        if not file.filename.endswith('.csv'):
            return render_template('group_import_result.html', 
                                  success=False, 
                                  message="File must be a CSV", 
                                  api_base_url=api_base_url)
        
        # Read the file
        csv_data = file.read().decode('utf-8')
        
        # Import the groups
        success, message, count = import_groups_from_csv(csv_data)
        
        return render_template('group_import_result.html', 
                              success=success, 
                              message=message, 
                              count=count, 
                              api_base_url=api_base_url)
    
    @app.route('/api/groups/approve/<group_id>', methods=['POST'])
    @login_required
    @group_required('moderators')
    def approve_group_route(group_id):
        """Approve a group"""
        return _process_group_action(group_id, "APPROVED")
    
    @app.route('/api/groups/delete/<group_id>', methods=['POST'])
    @login_required
    @group_required('moderators')
    def delete_group_route(group_id):
        """Delete a group"""
        return _process_group_action(group_id, None)
    
    @app.route('/api/groups/pending/<group_id>', methods=['POST'])
    @login_required
    @group_required('moderators')
    def set_group_pending_route(group_id):
        """Set a group to pending status"""
        return _process_group_action(group_id, "PENDING")
    
    @app.route('/api/groups/suggest-form', methods=['GET'])
    @login_required
    def group_suggest_form():
        """Serve the group suggestion form for HTMX inclusion"""
        # Create form with default values
        form = GroupForm()
        
        return render_template('group_form.html', form=form)
    
    @app.route('/api/groups/submit', methods=['POST'])
    @login_required
    def submit_group():
        """Handle group submission"""
        form = GroupForm()
        api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5001')
        
        if form.validate_on_submit():
            # Form is valid, process the data
            group_data = {
                'name': form.name.data,
                'website': form.website.data,
                'ical': form.ical.data,
                'fallback_url': form.fallback_url.data,
                'status': 'PENDING'  # New groups start as pending
            }
            
            # Save to database
            success, result = save_group_to_db(group_data)
            if success:
                group_data['id'] = result
                group_data['saved'] = True
            else:
                group_data['saved'] = False
                group_data['error'] = result
            
            # Return a response suitable for HTMX
            return render_template('group_submit_success.html', group=group_data, api_base_url=api_base_url)
        else:
            # Form has validation errors, redisplay with error messages
            return render_template('group_form.html', form=form, api_base_url=api_base_url)
    
    @app.route('/api/groups/edit-form/<group_id>', methods=['GET'])
    @login_required
    @group_required('localhost-moderators')
    def edit_group_form(group_id):
        """Serve the group edit form for HTMX inclusion"""
        api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
        
        # Get site slug to construct the full group ID
        site_slug = get_site_slug()
        
        # Construct the full group ID with site slug
        full_group_id = f"{site_slug}!{group_id}"
        
        # Get the group
        group = get_group_by_id(full_group_id)
        
        if not group:
            return jsonify({
                "success": False,
                "message": "Group not found"
            }), 404
        
        # Create form with group data
        form = GroupForm()
        form.name.data = group.get('name', '')
        form.website.data = group.get('website', '')
        form.ical.data = group.get('ical', '')
        form.fallback_url.data = group.get('fallback_url', '')
        
        return render_template('group_edit_form.html', form=form, group=group, api_base_url=api_base_url)
    
    @app.route('/api/groups/export-csv', methods=['GET'])
    @login_required
    @group_required('localhost-moderators')
    def export_groups_csv():
        """Export groups as CSV file"""
        # Get CSV data
        csv_data = export_groups_to_csv()
        
        # Create response with CSV data
        response = Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=groups.csv"}
        )
        
        return response
    
    @app.route('/api/groups/edit/<group_id>', methods=['POST'])
    @login_required
    @group_required('localhost-moderators')
    def edit_group(group_id):
        """Handle group edit form submission"""
        api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
        
        # Get site slug to construct the full group ID
        site_slug = get_site_slug()
        
        # Construct the full group ID with site slug
        full_group_id = f"{site_slug}!{group_id}"
        
        # Get the group
        group = get_group_by_id(full_group_id)
        
        if not group:
            return jsonify({
                "success": False,
                "message": "Group not found"
            }), 404
        
        # Create form and validate
        form = GroupForm()
        
        if form.validate_on_submit():
            # Form is valid, process the data
            group_data = {
                'name': form.name.data,
                'website': form.website.data,
                'ical': form.ical.data,
                'fallback_url': form.fallback_url.data
            }
            
            # Update the group
            success, message = update_group(full_group_id, group_data)
            
            if success:
                # Get all pending and approved groups
                pending_groups, _ = get_pending_groups(limit=100)
                approved_groups, _ = get_approved_groups(limit=100)
                
                # Combine groups for display
                groups = pending_groups + approved_groups
                
                return render_template('groups_manage.html', 
                                      groups=groups, 
                                      api_base_url=api_base_url, 
                                      message="Group updated successfully", 
                                      message_type="success")
            else:
                # Return with error message
                return render_template('group_edit_form.html', 
                                      form=form, 
                                      group=group, 
                                      api_base_url=api_base_url, 
                                      message=f"Error: {message}", 
                                      message_type="error")
        else:
            # Form validation failed
            return render_template('group_edit_form.html', 
                                  form=form, 
                                  group=group, 
                                  api_base_url=api_base_url, 
                                  message="Form validation failed", 
                                  message_type="error")