from flask import Blueprint, render_template, redirect, url_for, request, Response, flash, send_file
from .. import db
from ..models import Project
from datetime import datetime
import csv
from io import StringIO, BytesIO
import pandas as pd
import zipfile

projects_bp = Blueprint('projects', __name__)

@projects_bp.route('/projects', methods=['GET'])
def projects():
    selected_statuses = request.args.getlist('status_filter')

    if selected_statuses:
        projects = Project.query.filter(Project.Status.in_(selected_statuses)).order_by(Project.ProjectID).all()
    else:
        projects = Project.query.order_by(Project.ProjectID).all()

    # Get in-progress projects for the modal, sorted by ProjectID as well
    in_progress_projects = Project.query.filter_by(Status='In Progress').order_by(Project.ProjectID).all()

    return render_template(
        'projects.html',
        projects=projects,
        in_progress_projects=in_progress_projects
    )



@projects_bp.route('/projects/update_status', methods=['POST'])
def update_project_status():
    project_id = request.form.get('project_id')
    new_status = request.form.get('new_status')
    end_date_str = request.form.get('end_date')

    if not project_id or not new_status or not end_date_str:
        flash("All fields are required.", "error")
        return redirect(url_for('projects.projects'))

    try:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash("Invalid date format.", "error")
        return redirect(url_for('projects.projects'))

    project = Project.query.get(project_id)
    if not project:
        flash("Project not found.", "error")
        return redirect(url_for('projects.projects'))

    # Update project status and end date
    project.Status = new_status
    project.EndDate = end_date

    try:
        db.session.commit()
        flash(f"Project '{project.ProjectName}' updated successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to update project: {str(e)}", "error")

    return redirect(url_for('projects.projects'))


# Route to handle the project creation form submission

@projects_bp.route('/projects/create', methods=['POST'])  # Changed '/projects/create' to '/create'
def create_project():
    if request.method == 'POST':
        # Get the data from the form
        project_name = request.form.get('project_name')
        start_date = request.form.get('start_date')

        # Capitalize project name (first letter uppercase, rest lowercase)
        project_name = project_name.capitalize()

        # Check if project name is too long
        if len(project_name) > 100:
            flash("Project name is too long! Maximum length is 100 characters.", "error")
            return redirect(url_for('projects.projects'))  # Changed 'main.projects' to 'projects.projects'

        # Check if project already exists in the database
        existing_project = Project.query.filter_by(ProjectName=project_name).first()
        if existing_project:
            flash("A project with this name already exists.", "error")
            return redirect(url_for('projects.projects'))  # Changed 'main.projects' to 'projects.projects'

        # Convert start_date to a datetime object (if it's not empty)
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
        except ValueError:
            flash("Invalid start date format.", "error")
            return redirect(url_for('projects.projects'))  # Changed 'main.projects' to 'projects.projects'

        # Check if start_date is in the future
        if start_date and start_date > datetime.today():
            flash("Start date cannot be in the future.", "error")
            return redirect(url_for('projects.projects'))  # Changed 'main.projects' to 'projects.projects'

        # Create a new project record
        new_project = Project(
            ProjectName=project_name,
            StartDate=start_date,
            Status='In Progress'
        )

        # Add the project to the database
        db.session.add(new_project)
        db.session.commit()

        # Redirect to the project list page
        flash("Project created successfully!", "success")
        return redirect(url_for('projects.projects'))  # Changed 'main.projects' to 'projects.projects'

    return render_template('projects.html')  # Render the form again if not POST

@projects_bp.route('/projects/delete/<int:project_id>', methods=['POST'])  # Changed '/projects/delete/<int:project_id>' to '/delete/<int:project_id>'
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    try:
        db.session.delete(project)
        db.session.commit()
        flash('Project deleted successfully', 'success')
    except:
        flash('Error occurred while deleting the project', 'error')

    return redirect(url_for('projects.projects'))  # Changed 'main.projects' to 'projects.projects'
