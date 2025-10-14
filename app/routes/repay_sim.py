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

repayment_sim_bp = Blueprint('repayment_sim', __name__)

@repayment_sim_bp.route('/reports/automatic-repayment-simulation', methods=['GET'])
def simulate_repayment():
    end_date_str = request.args.get('end_date')
    selected_loan_number = request.args.get('loan_number', type=int)

    REPAYMENT_LIMIT = Decimal("500000")
    MIN_SPLIT = Decimal("50000")
    schedule = []

    all_loans = Loan.query.options(
        db.joinedload(Loan.tranches),
        db.joinedload(Loan.repayments),
        db.joinedload(Loan.adjustments),
        db.joinedload(Loan.project)
    ).order_by(Loan.LoanNumber).all()

    # Loans with outstanding balance
    unrepaid_loans = [
        loan for loan in all_loans
        if sum(Decimal(r.AmountPaid) for r in loan.repayments) <
           sum(Decimal(t.Amount) for t in loan.tranches)
    ]

    if not end_date_str or not selected_loan_number:
        return render_template(
            'simulate_repayment.html',
            schedule=[],
            selected_date=end_date_str,
            selected_loan_number=selected_loan_number,
            loans=unrepaid_loans
        )

    loan = next((l for l in unrepaid_loans if l.LoanNumber == selected_loan_number), None)
    if not loan:
        return render_template(
            'simulate_repayment.html',
            schedule=[],
            selected_date=end_date_str,
            selected_loan_number=selected_loan_number,
            loans=unrepaid_loans
        )

    # --- unpaid tranches ---
    unpaid_tranches = []
    for t in loan.tranches:
        tranche_repaid = sum(Decimal(r.AmountPaid) for r in loan.repayments if r.TrancheNumber == t.TrancheNumber)
        if tranche_repaid < Decimal(t.Amount):
            unpaid_tranches.append(t)

    unpaid_tranches.sort(key=lambda t: t.DateReceived)

    # --- adjustments and real repayments ---
    all_adjustments = [{'Amount': Decimal(a.Amount), 'Date': a.Date, 'TrancheNumber': a.TrancheNumber} for a in loan.adjustments]
    real_repayments = [{'Amount': Decimal(r.AmountPaid), 'DatePaid': r.DatePaid, 'TrancheNumber': r.TrancheNumber} for r in loan.repayments]

    # --- simulate repayment schedule ---
    day_schedules = []
    remaining_tranches = unpaid_tranches.copy()
    current_day = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    dummy_repayments = []

    while remaining_tranches:
        day_principal = Decimal("0")
        day_tranches = []
        for t in remaining_tranches:
            if day_principal + Decimal(t.Amount) <= REPAYMENT_LIMIT:
                day_tranches.append(t)
                day_principal += Decimal(t.Amount)
            elif day_principal >= REPAYMENT_LIMIT - MIN_SPLIT:
                break

        for t in day_tranches:
            remaining_tranches.remove(t)
            dummy_repayments.append({
                'Amount': Decimal(t.Amount),
                'DatePaid': current_day,
                'TrancheNumber': t.TrancheNumber
            })

        day_schedules.append({
            'date': current_day,
            'tranches': day_tranches,
            'principal_sum': day_principal
        })
        current_day += timedelta(days=1)

    all_repayments = real_repayments + dummy_repayments
    final_end_date = max(r['DatePaid'] for r in all_repayments)

    # --- calculate interest ---
    interest_map = {}
    for tranche in loan.tranches:
        tranche_repayments = [r for r in all_repayments if r['TrancheNumber'] == tranche.TrancheNumber]
        tranche_adjustments = [a for a in all_adjustments if a['TrancheNumber'] == tranche.TrancheNumber]
        result = calculate_tranche_interest(
            tranche,
            Decimal(loan.InterestRate),
            loan.Capitalization,
            final_end_date,
            repayments=tranche_repayments,
            adjustments=tranche_adjustments
        )
        interest_map[tranche.TrancheNumber] = result

    total_interest = sum(Decimal(i['PriorInterest']) + Decimal(i['YearlyInterest']) for i in interest_map.values())
    tax_on_interest = Decimal(math.floor(total_interest * Decimal("0.19")))
    interest_to_lender = (total_interest - tax_on_interest).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # --- fit interest into last day ---
    while True:
        last_day = day_schedules[-1]
        total_last_day = last_day['principal_sum'] + interest_to_lender
        if total_last_day <= REPAYMENT_LIMIT:
            break
        if not last_day['tranches']:
            break

        smallest_tranche = min(last_day['tranches'], key=lambda t: Decimal(t.Amount))
        last_day['tranches'].remove(smallest_tranche)
        last_day['principal_sum'] -= Decimal(smallest_tranche.Amount)

        for r in dummy_repayments:
            if r['TrancheNumber'] == smallest_tranche.TrancheNumber and r['DatePaid'] == last_day['date']:
                r['DatePaid'] = last_day['date'] + timedelta(days=1)

        next_day_date = last_day['date'] + timedelta(days=1)
        if len(day_schedules) > 1 and day_schedules[-1]['date'] == next_day_date:
            next_day = day_schedules[-1]
        else:
            next_day = {'date': next_day_date, 'tranches': [], 'principal_sum': Decimal("0")}
            day_schedules.append(next_day)

        next_day['tranches'].append(smallest_tranche)
        next_day['principal_sum'] += Decimal(smallest_tranche.Amount)

        # recalc interest
        all_repayments = real_repayments + dummy_repayments
        final_end_date = max(r['DatePaid'] for r in all_repayments)
        interest_map = {}
        for tranche in loan.tranches:
            tranche_repayments = [r for r in all_repayments if r['TrancheNumber'] == tranche.TrancheNumber]
            tranche_adjustments = [a for a in all_adjustments if a['TrancheNumber'] == tranche.TrancheNumber]
            result = calculate_tranche_interest(
                tranche,
                Decimal(loan.InterestRate),
                loan.Capitalization,
                final_end_date,
                repayments=tranche_repayments,
                adjustments=tranche_adjustments
            )
            interest_map[tranche.TrancheNumber] = result

        total_interest = sum(Decimal(i['PriorInterest']) + Decimal(i['YearlyInterest']) for i in interest_map.values())
        tax_on_interest = Decimal(math.floor(total_interest * Decimal("0.19")))
        interest_to_lender = (total_interest - tax_on_interest).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # --- final schedule ---
    schedule = []
    for i, day in enumerate(day_schedules):
        is_last_day = (i == len(day_schedules) - 1)
        for tranche in day['tranches']:
            principal = Decimal(tranche.Amount)
            interest = interest_to_lender if (is_last_day and tranche == day['tranches'][-1]) else Decimal("0")
            schedule.append({
                'date': day['date'],
                'LoanNumber': loan.LoanNumber,
                'TrancheNumber': tranche.TrancheNumber,
                'DateReceived': tranche.DateReceived,
                'Principal': principal.quantize(Decimal("0.01")),
                'Interest': interest.quantize(Decimal("0.01")),
            })

    return render_template(
        'simulate_repayment.html',
        schedule=schedule,
        selected_date=end_date_str,
        selected_loan_number=selected_loan_number,
        loans=unrepaid_loans,
        tax_on_interest=tax_on_interest,
        interest_to_lender=interest_to_lender
    )




@repayment_sim_bp.route('/reports/manual-repayment-simulation', methods=['GET', 'POST'])
def simulate_repayment_custom():
    all_loans = Loan.query.options(
        db.joinedload(Loan.tranches),
        db.joinedload(Loan.repayments),
        db.joinedload(Loan.adjustments),
        db.joinedload(Loan.project)
    ).order_by(Loan.LoanNumber).all()

    # loans with outstanding balance
    unrepaid_loans = [
        loan for loan in all_loans
        if sum(Decimal(r.AmountPaid) for r in loan.repayments) <
           sum(Decimal(t.Amount) for t in loan.tranches)
    ]

    selected_loan_number = None
    selected_loan = None
    tranches_left = []
    tax_on_interest = None
    interest_to_lender = None
    schedule = []

    if request.method == 'POST':
        selected_loan_number = request.form.get('loan_number', type=int)
        selected_loan = next((l for l in unrepaid_loans if l.LoanNumber == selected_loan_number), None)

        if not selected_loan:
            return redirect(url_for('report_bp.simulate_repayment_custom'))

        sorted_tranches = sorted(selected_loan.tranches, key=lambda t: t.TrancheNumber)

        repayment_dates = {}
        for t in sorted_tranches:
            tranche_repaid = sum(
                Decimal(r.AmountPaid) for r in selected_loan.repayments if r.TrancheNumber == t.TrancheNumber
            )
            if tranche_repaid < Decimal(t.Amount):
                amount_left = (Decimal(t.Amount) - tranche_repaid).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                date_str = request.form.get(f'repayment_date_{t.TrancheNumber}')
                try:
                    repayment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    repayment_date = None

                if repayment_date:
                    repayment_dates[t.TrancheNumber] = repayment_date

                tranches_left.append({
                    'tranche': t,
                    'amount_left': amount_left,
                    'repayment_date': repayment_date,
                    'received': t.DateReceived
                })

        if 'simulate' in request.form and repayment_dates:
            final_repayment_date = max(repayment_dates.values())
            total_interest = Decimal("0")

            for tranche in sorted_tranches:
                tranche_repayments = [
                    r for r in selected_loan.repayments if r.TrancheNumber == tranche.TrancheNumber
                ]
                all_repayments = [
                    {'Amount': Decimal(r.AmountPaid), 'DatePaid': r.DatePaid}
                    for r in tranche_repayments
                ]

                repaid_amount = sum(r['Amount'] for r in all_repayments)
                if repaid_amount < Decimal(tranche.Amount):
                    dummy_amount = (Decimal(tranche.Amount) - repaid_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    repayment_date = repayment_dates.get(tranche.TrancheNumber)
                    if repayment_date:
                        all_repayments.append({'Amount': dummy_amount, 'DatePaid': repayment_date})

                tranche_adjustments = [
                    a for a in selected_loan.adjustments if a.TrancheNumber == tranche.TrancheNumber
                ]
                all_adjustments = [
                    {'Amount': Decimal(a.Amount), 'Date': a.Date}
                    for a in tranche_adjustments
                ]

                result = calculate_tranche_interest(
                    tranche,
                    Decimal(selected_loan.InterestRate),
                    selected_loan.Capitalization,
                    final_repayment_date,  # use max of all form dates
                    repayments=all_repayments,
                    adjustments=all_adjustments
                )

                prior = Decimal(result['PriorInterest'])
                current = Decimal(result['YearlyInterest'])
                final_interest = (prior + current).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                total_interest += final_interest

            tax_on_interest = Decimal(math.floor(total_interest * Decimal("0.19")))
            interest_to_lender = (total_interest - tax_on_interest).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            schedule = [dict(
                TrancheNumber=item['tranche'].TrancheNumber,
                AmountLeft=item['amount_left'],
                RepaymentDate=item['repayment_date'].strftime('%Y-%m-%d') if item['repayment_date'] else '',
                DateReceived=item['received']
            ) for item in tranches_left]

    return render_template(
        'simulate_repayment_custom.html',
        loans=unrepaid_loans,
        selected_loan_number=selected_loan_number,
        selected_loan=selected_loan,
        tranches_left=tranches_left,
        tax_on_interest=tax_on_interest,
        interest_to_lender=interest_to_lender,
        schedule=schedule
    )