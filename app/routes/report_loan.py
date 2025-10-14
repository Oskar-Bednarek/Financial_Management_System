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

report_loan_bp = Blueprint('report_loan', __name__)

@report_loan_bp.route('/reportsss/loan-snapshot', methods=['GET'])
def loan_report():
    # Fetch all loans with project info for the dropdown
    all_loans = db.session.query(
        Loan.LoanNumber,
        Project.ProjectName,
        Loan.ProjectType
    ).join(Project).order_by(Loan.LoanNumber).all()

    loan_number = request.args.get('loan_number', type=int)
    if not loan_number:
        return render_template('loan_report.html', loans=all_loans, loan=None, report=[], fully_repaid=False)

    loan = Loan.query \
        .join(Project, Loan.ProjectID == Project.ProjectID) \
        .options(
            joinedload(Loan.tranches).joinedload(Tranche.repayments),
            joinedload(Loan.tranches).joinedload(Tranche.adjustments),
            joinedload(Loan.project)
        ) \
        .filter(Loan.LoanNumber == loan_number) \
        .first_or_404()

    # Collect repayment dates
    all_repayments = [
        repayment.DatePaid
        for tranche in loan.tranches
        for repayment in tranche.repayments
    ]
    latest_repayment = max(all_repayments) if all_repayments else None

    total_tranche_amount = sum(Decimal(t.Amount) for t in loan.tranches)
    total_repaid = sum(
        Decimal(r.AmountPaid) for t in loan.tranches for r in t.repayments
    )
    fully_repaid = total_repaid >= total_tranche_amount
    end_date = latest_repayment if fully_repaid else date.today()

    loan_principal = Decimal("0")
    loan_prior = Decimal("0")
    loan_current = Decimal("0")
    report_rows = []

    def to_cents(value):
        return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    for tranche in sorted(loan.tranches, key=lambda t: t.TrancheNumber):
        if tranche.DateReceived > end_date:
            continue

        repayments = [
            {'DatePaid': r.DatePaid, 'Amount': Decimal(r.AmountPaid)}
            for r in tranche.repayments
            if r.DatePaid <= end_date
        ]

        adjustments = [
            {'Date': a.Date, 'Amount': Decimal(a.Amount)}
            for a in tranche.adjustments
            if a.Date <= end_date
        ]

        result = calculate_tranche_interest(
            tranche=tranche,
            interest_rate=Decimal(loan.InterestRate),
            capitalization=loan.Capitalization,
            end_date=end_date,
            repayments=repayments,
            adjustments=adjustments
        )

        latest_repayment_date = max([r['DatePaid'] for r in repayments], default=None)

        # TotalDue should only include YearlyInterest if fully repaid
        yearly_part = Decimal(result['YearlyInterest']) if fully_repaid else Decimal("0")
        row_total_due = (
            Decimal(result['PrincipalLeft']) +
            Decimal(result['PriorInterest']) +
            yearly_part
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        report_rows.append({
            "TrancheNumber": tranche.TrancheNumber,
            "DateReceived": tranche.DateReceived,
            "LatestRepaymentDate": latest_repayment_date,
            "PrincipalLeft": to_cents(result['PrincipalLeft']),
            "PriorInterest": to_cents(result['PriorInterest']),
            "YearlyInterest": to_cents(result['YearlyInterest']),
            "TotalDue": row_total_due,
        })

        loan_principal += Decimal(result['PrincipalLeft'])
        loan_prior += Decimal(result['PriorInterest'])
        loan_current += Decimal(result['YearlyInterest'])

    # --- Totals ---
    total_interest = loan_prior + loan_current
    total_due = (
        loan_principal + loan_prior +
        (loan_current if fully_repaid else Decimal("0"))
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # --- keep original tax logic ---
    tax = Decimal(math.floor(total_interest * Decimal("0.19"))) if fully_repaid else None
    lender_interest = (total_interest - tax) if tax is not None else None

    return render_template(
        'loan_report.html',
        loans=all_loans,
        loan=loan,
        project=loan.project,
        end_date=end_date,
        report=report_rows,
        total_principal=loan_principal.quantize(Decimal("0.01")),
        total_prior=loan_prior.quantize(Decimal("0.01")),
        total_current=loan_current.quantize(Decimal("0.01")) if fully_repaid else None,
        total_interest=total_interest.quantize(Decimal("0.01")),  # still used for tax
        total_due=total_due,                                     # ✅ new total for the last column
        tax=tax,
        lender_interest=lender_interest.quantize(Decimal("0.01")) if lender_interest is not None else None,
        fully_repaid=fully_repaid
    )