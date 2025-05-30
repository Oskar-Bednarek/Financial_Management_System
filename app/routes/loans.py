from flask import Blueprint, render_template, redirect, url_for, request, flash
from .. import db
from ..models import Loan, Tranche, Repayment, Project
from datetime import date
from sqlalchemy import func
from datetime import datetime

loans_bp = Blueprint('loans', __name__)

@loans_bp.route("/loans")
def loans():
    id_name = db.session.query(Project.ProjectID, Project.ProjectName).all()
    selected_projects = request.args.getlist("project[]")
    selected_project_types = request.args.getlist("project_type[]")
    start_date_from = request.args.get("start_date_from")
    start_date_to = request.args.get("start_date_to")
    status_filter = request.args.get("status")  # "fully_repaid" or "not_repaid"

    # Subqueries
    tranche_subq = (
        db.session.query(
            Tranche.LoanNumber,
            func.coalesce(func.sum(Tranche.Amount), 0).label("TotalReceived")
        )
        .group_by(Tranche.LoanNumber)
        .subquery()
    )

    repayment_subq = (
        db.session.query(
            Repayment.LoanNumber,
            func.coalesce(func.sum(Repayment.AmountPaid), 0).label("TotalRepaid")
        )
        .group_by(Repayment.LoanNumber)
        .subquery()
    )

    # Main query
    query = (
        db.session.query(
            Loan,
            Project.ProjectName,
            func.coalesce(tranche_subq.c.TotalReceived, 0).label("TotalReceived"),
            func.coalesce(repayment_subq.c.TotalRepaid, 0).label("TotalRepaid")
        )
        .join(Project, Loan.ProjectID == Project.ProjectID)
        .outerjoin(tranche_subq, tranche_subq.c.LoanNumber == Loan.LoanNumber)
        .outerjoin(repayment_subq, repayment_subq.c.LoanNumber == Loan.LoanNumber)
    )

    # Apply filters
    if selected_projects:
        query = query.filter(Project.ProjectName.in_(selected_projects))

    if selected_project_types:
        query = query.filter(Loan.ProjectType.in_(selected_project_types))

    if start_date_from:
        query = query.filter(Loan.StartDate >= start_date_from)

    if start_date_to:
        query = query.filter(Loan.StartDate <= start_date_to)

    if status_filter == "fully_repaid":
        query = query.filter(func.coalesce(tranche_subq.c.TotalReceived, 0) == func.coalesce(repayment_subq.c.TotalRepaid, 0))
    elif status_filter == "not_repaid":
        query = query.filter(func.coalesce(tranche_subq.c.TotalReceived, 0) != func.coalesce(repayment_subq.c.TotalRepaid, 0))

    results = query.order_by(Loan.LoanNumber).all()

    # Format results
    loans_data = []
    for loan, project_name, total_received, total_repaid in results:
        fully_repaid = (total_received == total_repaid and total_received > 0)
        loans_data.append((loan, project_name, fully_repaid))

    # Dropdown/filter data
    all_projects = [p.ProjectName for p in db.session.query(Project.ProjectName).distinct()]
    all_types = [p.ProjectType for p in db.session.query(Loan.ProjectType).distinct()]
    all_statuses = ["fully_repaid", "not_repaid"]

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
        status_filter=status_filter
    )




@loans_bp.route("/loans/add", methods=["POST"])
def create_loan():
    try:
        project_name = request.form.get("project_name")
        project = db.session.query(Project).filter_by(ProjectName=project_name).first()
        if not project:
            flash("Selected project not found.", "danger")
            return redirect(url_for("loans.loans"))

        project_id = project.ProjectID
        total_amount = float(request.form.get("total_amount"))
        interest_rate = float(request.form.get("interest_rate"))
        capitalization = bool(request.form.get("capitalization"))
        project_type = request.form.get("project_type")

        # Parse and validate start date
        start_date_str = request.form.get("start_date")
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else None

        errors = []
        if interest_rate > 1:
            errors.append("Interest rate must be lowwer than 1.")
        if start_date and start_date > date.today():
            errors.append("Start date cannot be in the future.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return redirect(url_for("loans.loans"))

        # Generate LoanNumber
        latest_loan = db.session.query(Loan).order_by(Loan.LoanNumber.desc()).first()
        next_loan_number = (int(latest_loan.LoanNumber) + 1) if latest_loan else 1

        # Create new loan
        new_loan = Loan(
            LoanNumber=next_loan_number,
            ProjectID=project_id,
            TotalAmount=total_amount,
            InterestRate=interest_rate,  # Convert to decimal
            Capitalization=capitalization,
            ProjectType=project_type,
            StartDate=start_date
        )

        db.session.add(new_loan)
        db.session.commit()
        flash("Loan created successfully!", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error creating loan: {e}", "danger")

    return redirect(url_for("loans.loans"))


@loans_bp.route('/loans/delete/<int:loan_id>', methods=['POST'])
def delete_loan(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    try:
        db.session.delete(loan)
        db.session.commit()
        flash('Loan deleted successfully', 'success')
    except:
        flash('Error occurred while deleting the loan', 'error')

    return redirect(url_for('loans.loans'))
