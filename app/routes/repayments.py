from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from .. import db
from ..models import Tranche, Loan, Project, Repayment
from datetime import datetime, date
from sqlalchemy import func, not_
from sqlalchemy import and_
from app.functions import get_repayments_filtered, unpaid_loans_dropdown, create_repayment_record, get_unpaid_tranches_for_loan, delete_repayment_by_id

repayments_bp = Blueprint("repayments", __name__)



@repayments_bp.route("/repayments")
def repayments():
    selected_loan_numbers = request.args.getlist("loan[]")
    selected_statuses = request.args.getlist("status[]")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    repayment_data = get_repayments_filtered(
        selected_loan_numbers=selected_loan_numbers or None,
        selected_statuses=selected_statuses or None,
        date_from=date_from,
        date_to=date_to,
    )

    loans_dropdown = unpaid_loans_dropdown()

    return render_template(
        "repayments.html",
        repayments=repayment_data,
        loans_dropdown=loans_dropdown,
        selected_loan_numbers=selected_loan_numbers,
        selected_statuses=selected_statuses,
        date_from=date_from,
        date_to=date_to,
    )



@repayments_bp.route('/repayments/add', methods=['POST'])
def add_repayment():
    ok, msg = create_repayment_record(
        loan_number=request.form.get("loan_number"),
        tranche_number=request.form.get("tranche_number"),
        date_paid_str=request.form.get("date_paid"),
        amount_paid_str=request.form.get("amount_paid"),
    )
    flash(msg, "success" if ok else "error")
    return redirect(url_for("repayments.repayments"))




@repayments_bp.route('/repayments/get_tranches/<int:loan_number>', methods=['GET'])
def get_tranches(loan_number):
    tranche_list = get_unpaid_tranches_for_loan(loan_number)
    return jsonify(tranche_list)



@repayments_bp.route("/repayments/delete/<int:loan_number>/<int:tranche_number>/<date>", methods=["POST"])
def delete_repayment(loan_number, tranche_number, date):
    ok, msg = delete_repayment_by_id(loan_number, tranche_number, date)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("repayments.repayments"))