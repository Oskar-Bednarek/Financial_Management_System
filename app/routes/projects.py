from flask import Blueprint, render_template, redirect, url_for, request, Response, flash, send_file
from .. import db
from ..models import Project
from datetime import datetime
import csv
from io import StringIO, BytesIO
import pandas as pd
import zipfile
from app.functions import get_in_progress_projects, get_projects_filtered, parse_iso_date, update_project_status_and_end_date, create_project_record, delete_project_by_id


projects_bp = Blueprint('projects', __name__)

@projects_bp.route('/projects', methods=['GET'])
def projects():
    selected_statuses = request.args.getlist('status_filter')
    start_date_from = request.args.get('start_date_from')
    start_date_to   = request.args.get('start_date_to')
    end_date_from   = request.args.get('end_date_from')
    end_date_to     = request.args.get('end_date_to')

    projects = get_projects_filtered(
            statuses=selected_statuses or None,
            start_date_from=start_date_from,
            start_date_to=start_date_to,
            end_date_from=end_date_from,
            end_date_to=end_date_to,
            order_by=Project.ProjectID,
            direction="desc",
        )

    # Modal: oldest first (in-progress only)
    in_progress_projects = get_in_progress_projects(ascending=True)

    return render_template(
        'projects.html',
        projects=projects,
        in_progress_projects=in_progress_projects,
    )


@projects_bp.route('/projects/update_status', methods=['POST'])
def update_project_status():
    project_id = request.form.get('project_id')
    new_status = request.form.get('new_status')
    end_date_str = request.form.get('end_date')

    if not project_id or not new_status or not end_date_str:
        flash("All fields are required.", "error")
        return redirect(url_for('projects.projects'))

    end_date = parse_iso_date(end_date_str)
    if not end_date:
        flash("Invalid date format.", "error")
        return redirect(url_for('projects.projects'))

    ok, msg = update_project_status_and_end_date(project_id, new_status, end_date)
    flash(msg, "success" if ok else "error")
    return redirect(url_for('projects.projects'))


# Route to handle the project creation form submission
@projects_bp.route('/projects/create', methods=['POST'])
def create_project():
    project_name = request.form.get('project_name', '')
    start_date   = request.form.get('start_date')  # 'YYYY-MM-DD' or ''

    ok, msg = create_project_record(project_name, start_date)
    flash(msg, "success" if ok else "error")
    return redirect(url_for('projects.projects'))


@projects_bp.route('/projects/delete/<int:project_id>', methods=['POST'])
def delete_project(project_id):
    ok, msg = delete_project_by_id(project_id, protect_if_related=True)
    flash(msg, "success" if ok else "error")
    return redirect(url_for('projects.projects'))
