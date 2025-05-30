from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from .. import db
from ..models import Loan, Tranche, Repayment, Project, Adjustment
from datetime import date
from sqlalchemy import func
from datetime import datetime
from decimal import Decimal 

adjustments_bp = Blueprint('adjustments', __name__)


@adjustments_bp.route("/adjustments")
def adjustments():
    loan_numbers = request.args.getlist("loan[]", type=int)
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    query = db.session.query(Adjustment).order_by(Adjustment.Date.desc())

    if loan_numbers:
        query = query.filter(Adjustment.LoanNumber.in_(loan_numbers))

    if date_from:
        query = query.filter(Adjustment.Date >= date_from)

    if date_to:
        query = query.filter(Adjustment.Date <= date_to)

    adjustments = query.all()

    # Get loans that haven't been fully repaid, ordered by LoanNumber
    loans = (
        db.session.query(Loan.LoanNumber, Project.ProjectName, Loan.ProjectType)
        .join(Project, Loan.ProjectID == Project.ProjectID)
        .group_by(Loan.LoanNumber, Project.ProjectName, Loan.ProjectType)
        .order_by(Loan.LoanNumber)  # Order by LoanNumber (or any field you'd prefer)
        .all()
    )

    loans_dropdown = [
        {
            "LoanNumber": loan.LoanNumber,
            "ProjectName": loan.ProjectName,
            "ProjectType": loan.ProjectType
        }
        for loan in loans
    ]

    return render_template(
        "adjustments.html",
        adjustments=adjustments,
        loans_dropdown=loans_dropdown,
        selected_loan_numbers=loan_numbers,
        date_from=date_from,
        date_to=date_to
    )


@adjustments_bp.route("/adjustments/delete/<int:adjustment_id>", methods=["POST"])
def delete_adjustment(adjustment_id):
    adjustment = Adjustment.query.get_or_404(adjustment_id)
    db.session.delete(adjustment)
    db.session.commit()
    flash("Adjustment deleted successfully.", "success")
    return redirect(url_for("adjustments.adjustments"))




@adjustments_bp.route("/adjustments/get_tranches/<loan_number>")
def get_tranches(loan_number):
    tranches = (
        db.session.query(Tranche)
        .filter(Tranche.LoanNumber == loan_number)
        .order_by(Tranche.TrancheNumber)
        .all()
    )

    tranche_list = [
        {
            "TrancheNumber": t.TrancheNumber,
            "Amount": float(t.Amount)
        }
        for t in tranches
    ]
    return jsonify({"tranches": tranche_list})



@adjustments_bp.route('/adjustments/add', methods=['POST'])
def add_adjustment():
    try:
        loan_number = int(request.form['loan_number'])
        tranche_number = int(request.form['tranche_number'])
        date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        amount = Decimal(request.form['amount'])
        description = request.form.get('description', '')

        new_adjustment = Adjustment(
            LoanNumber=loan_number,
            TrancheNumber=tranche_number,
            Date=date,
            Amount=amount,
            Description=description
        )
        db.session.add(new_adjustment)
        db.session.commit()
        flash("Adjustment added successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding adjustment: {str(e)}", "error")

    return redirect(url_for('adjustments.adjustments'))