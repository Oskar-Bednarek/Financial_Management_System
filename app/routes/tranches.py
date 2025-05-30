from flask import Blueprint, render_template, redirect, url_for, request, flash
from .. import db
from ..models import Tranche, Loan, Project, Repayment
from datetime import datetime, date
from sqlalchemy import func, not_, and_

tranches_bp = Blueprint("tranches", __name__)



@tranches_bp.route("/tranches")
def tranches():
    # Get filters
    selected_loan_numbers = request.args.getlist("loan[]")
    status_filter = request.args.get("status")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

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

    loans_query = (
        db.session.query(
            Loan.LoanNumber,
            Project.ProjectName,
            Loan.ProjectType
        )
        .join(Project, Loan.ProjectID == Project.ProjectID)
        .outerjoin(total_tranche_amount, Loan.LoanNumber == total_tranche_amount.c.LoanNumber)
        .outerjoin(total_repaid_amount, Loan.LoanNumber == total_repaid_amount.c.LoanNumber)
        .filter(
            not_(
                (func.coalesce(total_repaid_amount.c.TotalRepaid, 0) == func.coalesce(total_tranche_amount.c.TotalLoanAmount, 0)) &
                (func.coalesce(total_repaid_amount.c.TotalRepaid, 0) > 0)
            )
        )
        .all()
    )

    loans_dropdown = [f"{l.LoanNumber} - {l.ProjectName} - {l.ProjectType}" for l in loans_query]

    loans = [
        {
            "LoanNumber": l.LoanNumber,
            "ProjectName": l.ProjectName,
            "ProjectType": l.ProjectType
        }
        for l in loans_query
    ]

    # Subquery: total repaid per tranche
    repayment_subq = (
        db.session.query(
            Repayment.LoanNumber,
            Repayment.TrancheNumber,
            func.coalesce(func.sum(Repayment.AmountPaid), 0).label("TotalRepaid")
        )
        .group_by(Repayment.LoanNumber, Repayment.TrancheNumber)
        .subquery()
    )

    # Base query
    query = (
        db.session.query(
            Tranche.LoanNumber,
            Tranche.TrancheNumber,
            Tranche.Amount,
            Tranche.DateReceived,
            func.coalesce(repayment_subq.c.TotalRepaid, 0).label("TotalRepaid")
        )
        .outerjoin(
            repayment_subq,
            (Tranche.LoanNumber == repayment_subq.c.LoanNumber) &
            (Tranche.TrancheNumber == repayment_subq.c.TrancheNumber)
        )
    )

    # Apply filters
    if selected_loan_numbers:
        query = query.filter(Tranche.LoanNumber.in_(selected_loan_numbers))

    if status_filter in ("repaid", "ongoing"):
        query = query.group_by(
            Tranche.LoanNumber,
            Tranche.TrancheNumber,
            Tranche.Amount,
            Tranche.DateReceived,
            repayment_subq.c.TotalRepaid
        )
        if status_filter == "repaid":
            query = query.having(func.coalesce(repayment_subq.c.TotalRepaid, 0) == Tranche.Amount)
        elif status_filter == "ongoing":
            query = query.having(func.coalesce(repayment_subq.c.TotalRepaid, 0) < Tranche.Amount)

    if date_from:
        query = query.filter(Tranche.DateReceived >= date_from)
    if date_to:
        query = query.filter(Tranche.DateReceived <= date_to)

    query = query.all()

    # Format results
    tranches_data = []
    for loan_number, tranche_number, amount, date_received, total_repaid in query:
        status = "Repaid" if amount == total_repaid else "Ongoing"
        tranches_data.append({
            'LoanNumber': loan_number,
            'TrancheNumber': tranche_number,
            'Amount': amount,
            'DateReceived': date_received,
            'Status': status  # ✅ Changed from 'FullyRepaid'
        })

    return render_template(
        "tranches.html",
        tranches=tranches_data,
        loans_dropdown=loans_dropdown,
        loans=loans,
        selected_loan_numbers=selected_loan_numbers,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to
    )



@tranches_bp.route("/tranches/create", methods=["POST"])
def add_tranche():
    loan_number = request.form.get("loan_number")
    tranche_date = request.form.get("tranche_date")
    amount = request.form.get("amount")

    # Validation: Check required fields
    if not tranche_date:
        flash(f"All fields are required tranche date {tranche_date}", "danger")
        return redirect(url_for("tranches.tranches"))

  # Validation: Check required fields
    if not loan_number:
        flash(f"All fields are required loanNumber {loan_number}", "danger")
        return redirect(url_for("tranches.tranches"))

  # Validation: Check required fields
    if not amount:
        flash(f"All fields are required amount", "danger")
        return redirect(url_for("tranches.tranches"))



    # Convert and validate date
    try:
        tranche_date_parsed = date.fromisoformat(tranche_date)
        if tranche_date_parsed > date.today():
            flash("Tranche date cannot be in the future", "danger")
            return redirect(url_for("tranches.tranches"))
    except ValueError as e:
        flash(f"Invalid date format: {e}", "danger")
        return redirect(url_for("tranches.tranches"))

    # Convert amount
    try:
        amount = float(amount)
        if amount <= 0:
            flash("Amount must be positive", "danger")
            return redirect(url_for("tranches.tranches"))
    except ValueError:
        flash("Invalid amount", "danger")
        return redirect(url_for("tranches.tranches"))

    # Fetch loan and current total received
    loan = Loan.query.get(loan_number)
    if not loan:
        flash("Loan not found", "danger")
        return redirect(url_for("tranches.tranches"))

    total_received = (
        db.session.query(func.coalesce(func.sum(Tranche.Amount), 0))
        .filter(Tranche.LoanNumber == loan.LoanNumber)
        .scalar()
    )

    # Validation: Check if new total would exceed loan amount
    # if total_received + amount > loan.TotalAmount:
    #     flash(f"Total received ({total_received + amount:,.2f}) exceeds loan amount ({loan.TotalAmount:,.2f})", "danger")
    #     return redirect(url_for("tranches.tranches"))
    # we did exceed the amount


    
    # Get next TrancheNumber
    last_tranche = (
        db.session.query(Tranche)
        .filter_by(LoanNumber=loan.LoanNumber)
        .order_by(Tranche.TrancheNumber.desc())
        .first()
    )
    next_tranche_number = 1 if not last_tranche else last_tranche.TrancheNumber + 1

    # Save new tranche
    new_tranche = Tranche(
        LoanNumber=loan.LoanNumber,
        TrancheNumber=next_tranche_number,
        DateReceived=tranche_date_parsed,
        Amount=amount
    )

    try:
        db.session.add(new_tranche)
        db.session.commit()
        flash("Tranche added successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error while saving tranche: {e}", "danger")

    return redirect(url_for("tranches.tranches"))



@tranches_bp.route("/tranches/delete/<int:loan_number>/<int:tranche_number>", methods=["POST"])
def delete_tranche(loan_number, tranche_number):
    # Fetch the tranche using both LoanNumber and TrancheNumber
    tranche = Tranche.query.filter_by(LoanNumber=loan_number, TrancheNumber=tranche_number).first_or_404()

    try:
        db.session.delete(tranche)
        db.session.commit()
        flash("Tranche deleted successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error occurred while deleting the tranche: {str(e)}", "danger")

    return redirect(url_for("tranches.tranches"))  # Redirect back to the tranches table page
