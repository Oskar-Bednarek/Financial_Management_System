from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from .. import db
from ..models import Tranche, Loan, Project, Repayment
from datetime import datetime, date
from sqlalchemy import func, not_

repayments_bp = Blueprint("repayments", __name__)


from sqlalchemy import and_




@repayments_bp.route("/repayments")
def repayments():
    # Get filter params
    selected_loan_numbers = request.args.getlist("loan[]")
    selected_statuses = request.args.getlist("status[]")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    # Base query
    base_query = (
        db.session.query(
            Repayment.LoanNumber,
            Repayment.TrancheNumber,
            Repayment.DatePaid,
            Repayment.AmountPaid,
            Tranche.Amount.label("TrancheAmount")
        )
        .outerjoin(
            Tranche,
            (Repayment.LoanNumber == Tranche.LoanNumber) &
            (Repayment.TrancheNumber == Tranche.TrancheNumber)
        )
    )

    # Apply filters
    if selected_loan_numbers:
        base_query = base_query.filter(Repayment.LoanNumber.in_(selected_loan_numbers))

    if date_from:
        base_query = base_query.filter(Repayment.DatePaid >= date_from)
    if date_to:
        base_query = base_query.filter(Repayment.DatePaid <= date_to)

    results = base_query.all()

    # Process repayments with derived status
    repayment_data = []
    for r in results:
        tranche_amount = r.TrancheAmount or 0.0
        if tranche_amount:
            status = "Full Repayment" if r.AmountPaid >= tranche_amount else "Partial Repayment"
        else:
            status = "Unknown"

        if selected_statuses and status not in selected_statuses:
            continue

        repayment_data.append({
            "LoanNumber": r.LoanNumber,
            "TrancheNumber": r.TrancheNumber,
            "DatePaid": r.DatePaid,
            "AmountPaid": r.AmountPaid,
            "Status": status
        })

    # Subquery: Total tranche amount per loan
    total_tranche_amount = (
        db.session.query(
            Tranche.LoanNumber,
            func.coalesce(func.sum(Tranche.Amount), 0).label("TotalLoanAmount")
        )
        .group_by(Tranche.LoanNumber)
        .subquery()
    )

    # Subquery: Total repaid per loan
    total_repaid_amount = (
        db.session.query(
            Repayment.LoanNumber,
            func.coalesce(func.sum(Repayment.AmountPaid), 0).label("TotalRepaid")
        )
        .group_by(Repayment.LoanNumber)
        .subquery()
    )

    unpaid_loans = (
        db.session.query(
            Loan.LoanNumber,
            Project.ProjectName,
            Loan.ProjectType
        )
        .join(Project, Loan.ProjectID == Project.ProjectID)
        .outerjoin(total_tranche_amount, Loan.LoanNumber == total_tranche_amount.c.LoanNumber)  # Outer join for tranches
        .outerjoin(total_repaid_amount, Loan.LoanNumber == total_repaid_amount.c.LoanNumber)  # Outer join for repayments
        .filter(
            not_(
                (func.coalesce(total_repaid_amount.c.TotalRepaid, 0) == func.coalesce(total_tranche_amount.c.TotalLoanAmount, 0)) &
                (func.coalesce(total_repaid_amount.c.TotalRepaid, 0) > 0)
            )
        )
        .all()
    )

    loans_dropdown = [
        {
            "LoanNumber": loan.LoanNumber,
            "ProjectName": loan.ProjectName,
            "ProjectType": loan.ProjectType
        }
        for loan in unpaid_loans
    ]

    return render_template(
        "repayments.html",
        repayments=repayment_data,
        loans_dropdown=loans_dropdown,
        selected_loan_numbers=selected_loan_numbers,
        selected_statuses=selected_statuses,
        date_from=date_from,
        date_to=date_to
    )



@repayments_bp.route('/repayments/add', methods=['POST'])
def add_repayment():
    loan_number = request.form.get("loan_number")
    tranche_number = request.form.get("tranche_number")
    date_paid = request.form.get("date_paid")
    amount_paid = float(request.form.get("amount_paid"))

    # Get the tranche
    tranche = Tranche.query.filter_by(LoanNumber=loan_number, TrancheNumber=tranche_number).first()

    if not tranche:
        flash("Invalid tranche selected.", "error")
        return redirect(url_for("repayments.repayments"))

    # Check if date_paid is after or on Tranche.DateIssued
    if date_paid < tranche.DateReceived.isoformat():
        flash("Repayment date cannot be before the tranche date.", "error")
        return redirect(url_for("repayments.repayments"))

    # Get total already repaid
    total_repaid = db.session.query(
        func.coalesce(func.sum(Repayment.AmountPaid), 0)
    ).filter_by(
        LoanNumber=loan_number,
        TrancheNumber=tranche_number
    ).scalar()

    remaining_amount = tranche.Amount - total_repaid

    if amount_paid > remaining_amount:
        flash(f"Repayment exceeds remaining amount (${remaining_amount:.2f}) for this tranche.", "error")
        return redirect(url_for("repayments.repayments"))

    # All checks passed, create repayment
    new_repayment = Repayment(
        LoanNumber=loan_number,
        TrancheNumber=tranche_number,
        DatePaid=date_paid,
        AmountPaid=amount_paid
    )

    db.session.add(new_repayment)
    db.session.commit()

    flash("Repayment added successfully!", "success")
    return redirect(url_for("repayments.repayments"))




@repayments_bp.route('/repayments/get_tranches/<loan_number>', methods=['GET'])
def get_tranches(loan_number):
    # Fetch all tranches for the selected loan that are not fully repaid
    tranches = (
        db.session.query(
            Tranche.TrancheNumber,
            Tranche.Amount,
            db.func.coalesce(db.func.sum(Repayment.AmountPaid), 0).label('TotalRepayment')
        )
        .outerjoin(Repayment, (Tranche.LoanNumber == Repayment.LoanNumber) & (Tranche.TrancheNumber == Repayment.TrancheNumber))
        .filter(Tranche.LoanNumber == loan_number)
        .group_by(Tranche.TrancheNumber, Tranche.Amount)
        .having(db.func.coalesce(db.func.sum(Repayment.AmountPaid), 0) < Tranche.Amount)
        .all()
    )

    # Create a list of tranches with the remaining amount to repay
    tranche_list = [
        {
            "TrancheNumber": tranche.TrancheNumber,
            "RemainingAmount": tranche.Amount - tranche.TotalRepayment
        }
        for tranche in tranches
    ]

    return jsonify(tranche_list)


@repayments_bp.route("/repayments/delete/<int:loan_number>/<int:tranche_number>/<date>", methods=["POST"])
def delete_repayment(loan_number, tranche_number, date):
    repayment = Repayment.query.filter_by(
        LoanNumber=loan_number,
        TrancheNumber=tranche_number,
        DatePaid=date
    ).first()
    if repayment:
        db.session.delete(repayment)
        db.session.commit()
        flash("Repayment deleted successfully.", "success")
    else:
        flash("Repayment not found.", "error")
    return redirect(url_for("repayments.repayments"))