from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from .. import db
from ..models import Loan, Tranche, Repayment, Project, Adjustment
from datetime import date
from sqlalchemy import func
from datetime import datetime
from decimal import Decimal 
from app.functions import get_adjustments_filtered, loans_dropdown_unpaid_or_all, delete_adjustment_by_id, get_tranches_for_loan_all, create_adjustment_record

adjustments_bp = Blueprint('adjustments', __name__)


@adjustments_bp.route("/adjustments")
def adjustments():
    loan_numbers = request.args.getlist("loan[]", type=int)
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    adjustments = get_adjustments_filtered(
        loan_numbers=loan_numbers or None,
        date_from=date_from,
        date_to=date_to,
    )

    # choose unpaid_only=True to mirror tranches/repayments filters,
    # or set to False if you want all loans available in this page
    loans_dropdown = loans_dropdown_unpaid_or_all(unpaid_only=True)

    return render_template(
        "adjustments.html",
        adjustments=adjustments,
        loans_dropdown=loans_dropdown,
        selected_loan_numbers=loan_numbers,
        date_from=date_from,
        date_to=date_to,
    )


@adjustments_bp.route("/adjustments/delete/<int:adjustment_id>", methods=["POST"])
def delete_adjustment(adjustment_id):
    success, message = delete_adjustment_by_id(adjustment_id)
    flash(message, "success" if success else "error")
    return redirect(url_for("adjustments.adjustments"))




@adjustments_bp.route("/adjustments/get_tranches/<int:loan_number>")
def get_tranches(loan_number):
    return jsonify({"tranches": get_tranches_for_loan_all(loan_number)})



@adjustments_bp.route('/adjustments/add', methods=['POST'])
def add_adjustment():
    ok, msg = create_adjustment_record(
        loan_number=request.form.get('loan_number'),
        tranche_number=request.form.get('tranche_number'),
        date_str=request.form.get('date'),
        amount_str=request.form.get('amount'),
        description=request.form.get('description', ''),
    )
    flash(msg, "success" if ok else "error")
    return redirect(url_for('adjustments.adjustments'))