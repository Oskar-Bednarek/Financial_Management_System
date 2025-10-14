from flask import Blueprint, render_template, redirect, url_for, request, flash
from .. import db
from ..models import Loan, Tranche, Repayment, Project
from datetime import date
from sqlalchemy import func
from datetime import datetime
from app.functions import (
    get_loans_with_totals,
    distinct_project_names,
    create_loan_record,
    delete_loan_by_id,
    in_progress_project_names
)


loans_bp = Blueprint('loans', __name__)

@loans_bp.route("/loans")
def loans():
    id_name = in_progress_project_names()

    selected_projects = request.args.getlist("project[]")
    selected_project_types = request.args.getlist("project_type[]")
    start_date_from = request.args.get("start_date_from")
    start_date_to = request.args.get("start_date_to")
    status_filter = request.args.get("status")  # "fully_repaid" | "ongoing"

    loans_data = get_loans_with_totals(
        selected_projects=selected_projects or None,
        selected_project_types=selected_project_types or None,
        start_date_from=start_date_from,
        start_date_to=start_date_to,
        status_filter=status_filter,
        order_desc=False,  # keep ascending LoanNumber like before
    )

    all_projects = distinct_project_names()
    all_types = ['Building Process', 'Property', 'Apartment']
    all_statuses = ["Fully_repaid", "Ongoing"]

    return render_template(
        "loans.html",
        loans=loans_data,
        projects=all_projects,
        project_types=all_types,
        selected_projects=selected_projects,
        selected_project_types=selected_project_types,
        start_date_from=start_date_from,
        start_date_to=start_date_to,
        id_name=id_name,
        all_statuses=all_statuses,
        status_filter=status_filter,
    )




@loans_bp.route("/loans/add", methods=["POST"])
def create_loan():
    ok, msg = create_loan_record(
        project_name=request.form.get("project_name", ""),
        total_amount_str=request.form.get("total_amount", ""),
        interest_rate_str=request.form.get("interest_rate", ""),
        capitalization_str=request.form.get("capitalization"),  # None if unchecked
        project_type=request.form.get("project_type"),
        start_date_str=request.form.get("start_date"),
    )
    flash(msg, "success" if ok else "danger")
    return redirect(url_for("loans.loans"))


@loans_bp.route('/loans/delete/<int:loan_id>', methods=['POST'])
def delete_loan(loan_id):
    ok, msg = delete_loan_by_id(loan_id, protect_if_related=True)
    flash(msg, "success" if ok else "error")
    return redirect(url_for('loans.loans'))
