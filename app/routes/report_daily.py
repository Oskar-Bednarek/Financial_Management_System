from flask import Blueprint, render_template, request, redirect, url_for
from datetime import datetime
import datetime
from ..models import db, Loan, Tranche, Project, Repayment
from collections import defaultdict
from datetime import datetime, date, timedelta
from sqlalchemy.orm import joinedload
import math
from sqlalchemy import func
from decimal import Decimal, ROUND_HALF_UP
from app.functions import calculate_tranche_interest

report_daily_bp = Blueprint('report_daily', __name__)


@report_daily_bp.route('/reportssss/daily-summary', methods=['GET'])
def custom_date_report():
    date_str = request.args.get('date')
    if date_str:
        try:
            end_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            end_date = date.today()
    else:
        end_date = date.today()

    loans = Loan.query.options(
        joinedload(Loan.tranches).joinedload(Tranche.repayments),
        joinedload(Loan.tranches).joinedload(Tranche.adjustments),
        joinedload(Loan.project)
    ).all()

    loans = sorted(loans, key=lambda l: l.LoanNumber)

    report_rows = []
    total_principal = Decimal("0")
    total_prior_interest = Decimal("0")

    for loan in loans:
        loan_number = loan.LoanNumber
        interest_rate = Decimal(loan.InterestRate)  # ensure Decimal
        capitalization = loan.Capitalization
        project_name = loan.project.ProjectName if loan.project else ""
        project_type = loan.ProjectType if loan else ""

        total_tranche_amount = sum(Decimal(t.Amount) for t in loan.tranches if t.DateReceived <= end_date)
        total_repaid = sum(
            Decimal(r.AmountPaid)
            for t in loan.tranches
            for r in t.repayments
            if r.DatePaid <= end_date
        )

        if total_repaid >= total_tranche_amount:
            continue

        loan_principal = Decimal("0")
        loan_prior = Decimal("0")

        tranches = sorted(loan.tranches, key=lambda t: t.TrancheNumber)

        for tranche in tranches:
            if tranche.DateReceived > end_date:
                continue

            repayments = [
                {
                    'DatePaid': repayment.DatePaid,
                    'Amount': Decimal(repayment.AmountPaid)
                }
                for repayment in tranche.repayments
                if repayment.DatePaid <= end_date
            ]

            adjustments = [
                {
                    'Date': adjustment.Date,
                    'Amount': Decimal(adjustment.Amount)
                }
                for adjustment in tranche.adjustments
                if adjustment.Date <= end_date
            ]

            result = calculate_tranche_interest(
                tranche=tranche,
                interest_rate=interest_rate,
                capitalization=capitalization,
                end_date=end_date,
                repayments=repayments,
                adjustments=adjustments
            )

            report_rows.append({
                "LoanNumber": loan_number,
                "TrancheNumber": tranche.TrancheNumber,
                "PrincipalLeft": round(result['PrincipalLeft'], 2),
                "PriorInterest": round(result['PriorInterest'], 2),
                "YearlyInterest": None,
                "TotalDue": round(result['PrincipalLeft'] + result['PriorInterest'], 2),
                "ProjectName": project_name,
                "ProjectType": project_type,
                "is_summary": False
            })

            loan_principal += result['PrincipalLeft']
            loan_prior += result['PriorInterest']

        if loan_principal > 0:
            report_rows.append({
                "LoanNumber": loan_number,
                "TrancheNumber": "Total",
                "PrincipalLeft": round(loan_principal, 2),
                "PriorInterest": round(loan_prior, 2),
                "YearlyInterest": None,
                "TotalDue": round(loan_principal + loan_prior, 2),
                "ProjectName": project_name,
                "ProjectType": project_type,
                "is_summary": True
            })

        total_principal += loan_principal
        total_prior_interest += loan_prior

    report_rows.append({
        "LoanNumber": "Grand Total",
        "TrancheNumber": "",
        "PrincipalLeft": round(total_principal, 2),
        "PriorInterest": round(total_prior_interest, 2),
        "YearlyInterest": None,
        "TotalDue": round(total_principal + total_prior_interest, 2),
        "ProjectName": "",
        "ProjectType": "",
        "is_summary": True
    })

    return render_template('custom_date_report.html', report=report_rows, report_date=end_date)