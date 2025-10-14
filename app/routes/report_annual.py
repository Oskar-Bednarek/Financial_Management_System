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

report_annual_bp = Blueprint('report_annual', __name__)


@report_annual_bp.route('/reportssss/annual-summary', methods=['GET'])
def annual_summary():
    year = request.args.get('year', (datetime.now().year - 1), type=int)
    view = request.args.get('view', 'summarized')  # Default to summarized view
    end_date = date(year, 12, 31)

    loans = Loan.query.options(
        joinedload(Loan.project),  # load project to get ProjectName
        joinedload(Loan.tranches).joinedload(Tranche.repayments),
        joinedload(Loan.tranches).joinedload(Tranche.adjustments)
    ).all()

    # Sort loans by LoanNumber
    loans = sorted(loans, key=lambda l: l.LoanNumber)

    report_rows = []
    total_principal = Decimal("0")
    total_prior_interest = Decimal("0")
    total_current_interest = Decimal("0")

    for loan in loans:
        loan_number = loan.LoanNumber
        project_name = loan.project.ProjectName if loan.project else ''
        project_type = loan.ProjectType
        interest_rate = loan.InterestRate
        capitalization = loan.Capitalization

        # --- Filtering fully repaid loans ---
        total_tranche_amount = sum(Decimal(t.Amount) for t in loan.tranches if t.DateReceived <= end_date)
        total_repaid = sum(
            Decimal(r.AmountPaid)
            for t in loan.tranches
            for r in t.repayments
            if r.DatePaid <= end_date
        )

        if total_repaid >= total_tranche_amount:
            continue  # Loan is fully repaid by report date

        loan_principal = Decimal("0")
        loan_prior = Decimal("0")
        loan_current = Decimal("0")

        # Sort tranches by TrancheNumber
        tranches = sorted(loan.tranches, key=lambda t: t.TrancheNumber)

        for tranche in tranches:
            if tranche.DateReceived > end_date:
                continue

            # Get repayments for this tranche
            repayments = [
                {
                    'DatePaid': repayment.DatePaid,
                    'Amount': Decimal(repayment.AmountPaid)
                }
                for repayment in tranche.repayments
                if repayment.DatePaid <= end_date
            ]

            # Get adjustments for this tranche
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
                interest_rate=Decimal(interest_rate),  # ensure Decimal
                capitalization=capitalization,
                end_date=end_date,
                repayments=repayments,
                adjustments=adjustments
            )

            report_rows.append({
                "LoanNumber": loan_number,
                "ProjectName": project_name,
                "ProjectType": project_type,
                "TrancheNumber": tranche.TrancheNumber,
                "PrincipalLeft": round(result['PrincipalLeft'], 2),
                "PriorInterest": round(result['PriorInterest'], 2),
                "YearlyInterest": round(result['YearlyInterest'], 2),
                "TotalDue": round(result['PrincipalLeft'] + result['PriorInterest'] + result['YearlyInterest'], 2),
                "is_summary": False
            })

            loan_principal += result['PrincipalLeft']
            loan_prior += result['PriorInterest']
            loan_current += result['YearlyInterest']

        # Loan-level total row
        if loan_principal > 0:
            report_rows.append({
                "LoanNumber": loan_number,
                "ProjectName": project_name,
                "ProjectType": project_type,
                "TrancheNumber": "Total",
                "PrincipalLeft": round(loan_principal, 2),
                "PriorInterest": round(loan_prior, 2),
                "YearlyInterest": round(loan_current, 2),
                "TotalDue": round(loan_principal + loan_prior + loan_current, 2),
                "is_summary": True
            })

        total_principal += loan_principal
        total_prior_interest += loan_prior
        total_current_interest += loan_current

    # Grand total row
    report_rows.append({
        "LoanNumber": "Grand Total",
        "ProjectName": "",
        "ProjectType": "",
        "TrancheNumber": "",
        "PrincipalLeft": round(total_principal, 2),
        "PriorInterest": round(total_prior_interest, 2),
        "YearlyInterest": round(total_current_interest, 2),
        "TotalDue": round(total_principal + total_prior_interest + total_current_interest, 2),
        "is_summary": True
    })

    return render_template(
        'yearly_report.html',
        report=report_rows,
        year=year,
        view=view
    )