from flask import Blueprint, render_template, redirect, url_for, request, flash
from .. import db
from ..models import Tranche, Loan, Project, Repayment
from datetime import datetime, date
from sqlalchemy import func, not_, and_
from app.functions import loan_dropdown_options, get_tranches_filtered, create_tranche_record, delete_tranche_by_id


tranches_bp = Blueprint("tranches", __name__)



@tranches_bp.route("/tranches")
def tranches():
    selected_loan_numbers = request.args.getlist("loan[]")
    status_filter = request.args.get("status")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    loans_dropdown, loans = loan_dropdown_options()
    tranches_data = get_tranches_filtered(
        selected_loan_numbers=selected_loan_numbers or None,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
    )

    return render_template(
        "tranches.html",
        tranches=tranches_data,
        loans_dropdown=loans_dropdown,
        loans=loans,
        selected_loan_numbers=selected_loan_numbers,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
    )



@tranches_bp.route("/tranches/create", methods=["POST"])
def add_tranche():
    ok, msg = create_tranche_record(
        loan_number=request.form.get("loan_number"),
        tranche_date_str=request.form.get("tranche_date"),
        amount_str=request.form.get("amount"),
    )
    flash(msg, "success" if ok else "danger")
    return redirect(url_for("tranches.tranches"))



@tranches_bp.route("/tranches/delete/<int:loan_number>/<int:tranche_number>", methods=["POST"])
def delete_tranche(loan_number, tranche_number):
    ok, msg = delete_tranche_by_id(loan_number, tranche_number)
    flash(msg, "success" if ok else "danger")
    return redirect(url_for("tranches.tranches"))
