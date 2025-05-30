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


report_bp = Blueprint('report', __name__)


def calculate_tranche_interest(
    tranche,
    interest_rate,
    capitalization,
    end_date,
    repayments=None,
    adjustments=None
):
    repayments = repayments or []
    adjustments = adjustments or []

    start_date = tranche.DateReceived
    original_principal = tranche.Amount
    remaining_principal = original_principal
    capitalized_interest = 0.0
    prior_interest = 0.0
    current_year_interest = 0.0

    current_year = end_date.year
    start_year = start_date.year

    # Organize repayments and adjustments by year
    repayments_by_year = defaultdict(list)
    for r in repayments:
        repayments_by_year[r['DatePaid'].year].append(r)

    adjustments_by_year = defaultdict(float)
    for a in adjustments:
        adjustments_by_year[a['Date'].year] += a['Amount']

    for year in range(start_year, current_year + 1):
        yearly_interest = 0.0
        year_start = max(start_date, date(year-1, 12, 31))
        year_end = min(end_date, date(year, 12, 31))

        # Get repayments within the year and sort by date
        year_repayments = sorted(repayments_by_year.get(year, []), key=lambda r: r['DatePaid'])

        # Split year into periods based on repayments
        period_start = year_start
        for repayment in year_repayments:
            period_end = min(repayment['DatePaid'], year_end)
            if period_end > period_start and remaining_principal > 0:
                days = (period_end - period_start).days# + 1
                fraction = days / 366
                yearly_interest += remaining_principal * interest_rate * fraction
                period_start = period_end
            # Apply repayment
            remaining_principal -= repayment['Amount']
            remaining_principal = max(0.0, remaining_principal)

        # Final period to year_end
        if remaining_principal > 0 and period_start < year_end:
            days = (year_end - period_start).days# + 1
            fraction = days / 366
            yearly_interest += remaining_principal * interest_rate * fraction

        # Interest on capitalized interest
        cap_days = (min(year_end, end_date) - year_start).days
        cap_fraction = cap_days / 366
        if capitalization:
            yearly_interest += capitalized_interest * interest_rate * cap_fraction
            capitalized_interest += yearly_interest  # Only update if capitalization is on

        # Add adjustments at the end of the year to yearly interest
        yearly_adjustment = adjustments_by_year.get(year, 0.0)
        yearly_interest += yearly_adjustment

        # Track prior/current year interest
        if year < current_year:
            prior_interest += yearly_interest
        elif year == current_year:
            current_year_interest += yearly_interest

    return {
        'PrincipalLeft': round(remaining_principal, 2),
        'PriorInterest': round(prior_interest, 2),
        'YearlyInterest': round(current_year_interest, 2),
    }





@report_bp.route('/reports/annual-summary', methods=['GET'])
def yearly_report():
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
    total_principal = 0.0
    total_prior_interest = 0.0
    total_current_interest = 0.0

    for loan in loans:
        loan_number = loan.LoanNumber
        project_name = loan.project.ProjectName if loan.project else ''  # safely get ProjectName
        project_type = loan.ProjectType  # from Loan table
        interest_rate = loan.InterestRate
        capitalization = loan.Capitalization

        # --- Filtering fully repaid loans ---
        total_tranche_amount = sum(t.Amount for t in loan.tranches if t.DateReceived <= end_date)
        total_repaid = sum(
            r.AmountPaid
            for t in loan.tranches
            for r in t.repayments
            if r.DatePaid <= end_date
        )

        if total_repaid >= total_tranche_amount:
            continue  # Loan is fully repaid by report date

        loan_principal = 0.0
        loan_prior = 0.0
        loan_current = 0.0

        # Sort tranches by TrancheNumber
        tranches = sorted(loan.tranches, key=lambda t: t.TrancheNumber)

        for tranche in tranches:
            if tranche.DateReceived > end_date:
                continue

            # Get repayments for this tranche
            repayments = [
                {
                    'DatePaid': repayment.DatePaid,
                    'Amount': float(repayment.AmountPaid)
                }
                for repayment in tranche.repayments
                if repayment.DatePaid <= end_date
            ]

            # Get adjustments for this tranche
            adjustments = [
                {
                    'Date': adjustment.Date,
                    'Amount': float(adjustment.Amount)
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
                "ProjectName": project_name,
                "ProjectType": project_type,
                "TrancheNumber": tranche.TrancheNumber,
                "PrincipalLeft": result['PrincipalLeft'],
                "PriorInterest": result['PriorInterest'],
                "YearlyInterest": result['YearlyInterest'],
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
        view=view  # Pass view to template
    )





@report_bp.route('/reports/loan-snapshot', methods=['GET'])
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

    all_repayments = [
        repayment.DatePaid
        for tranche in loan.tranches
        for repayment in tranche.repayments
    ]
    latest_repayment = max(all_repayments) if all_repayments else None

    total_tranche_amount = sum(t.Amount for t in loan.tranches)
    total_repaid = sum(
        r.AmountPaid for t in loan.tranches for r in t.repayments
    )
    fully_repaid = total_repaid >= total_tranche_amount
    end_date = latest_repayment if fully_repaid else date.today()

    loan_principal = 0.0
    loan_prior = 0.0
    loan_current = 0.0
    report_rows = []

    for tranche in sorted(loan.tranches, key=lambda t: t.TrancheNumber):
        if tranche.DateReceived > end_date:
            continue

        repayments = [
            {'DatePaid': r.DatePaid, 'Amount': float(r.AmountPaid)}
            for r in tranche.repayments
            if r.DatePaid <= end_date
        ]

        adjustments = [
            {'Date': a.Date, 'Amount': float(a.Amount)}
            for a in tranche.adjustments
            if a.Date <= end_date
        ]

        result = calculate_tranche_interest(
            tranche=tranche,
            interest_rate=loan.InterestRate,
            capitalization=loan.Capitalization,
            end_date=end_date,
            repayments=repayments,
            adjustments=adjustments
        )

        latest_repayment_date = max([r['DatePaid'] for r in repayments], default=None)

        def to_cents(value):
            return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        report_rows.append({
            "TrancheNumber": tranche.TrancheNumber,
            "DateReceived": tranche.DateReceived,
            "LatestRepaymentDate": latest_repayment_date,
            "PrincipalLeft": Decimal(result['PrincipalLeft']),  # assuming integer, but keep as Decimal
            "PriorInterest": to_cents(result['PriorInterest']),
            "YearlyInterest": to_cents(result['YearlyInterest']),
            "TotalDue": (
                Decimal(result['PrincipalLeft']) +
                to_cents(result['PriorInterest']) +
                to_cents(result['YearlyInterest'])
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        })

        loan_principal += result['PrincipalLeft']
        loan_prior += round(result['PriorInterest'],2)
        loan_current += round(result['YearlyInterest'],2)

    total_interest = loan_prior + loan_current
    tax = math.floor(total_interest * 0.19) if fully_repaid else None
    lender_interest = total_interest - tax if fully_repaid else None

    return render_template(
        'loan_report.html',
        loans=all_loans,
        loan=loan,
        project=loan.project,  # add this line
        end_date=end_date,
        report=report_rows,
        total_principal=round(loan_principal, 2),
        total_prior=round(loan_prior, 2),
        total_current=round(loan_current, 2),
        total_interest=round(total_interest, 2),
        tax=tax,
        lender_interest=round(lender_interest, 2) if lender_interest is not None else None,
        fully_repaid=fully_repaid
    )

@report_bp.route('/reports/daily-summary', methods=['GET'])
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
        joinedload(Loan.project)  # <-- added project loading
    ).all()

    loans = sorted(loans, key=lambda l: l.LoanNumber)

    report_rows = []
    total_principal = 0.0
    total_prior_interest = 0.0

    for loan in loans:
        loan_number = loan.LoanNumber
        interest_rate = loan.InterestRate
        capitalization = loan.Capitalization
        project_name = loan.project.ProjectName if loan.project else ""
        project_type = loan.ProjectType if loan else ""

        total_tranche_amount = sum(t.Amount for t in loan.tranches if t.DateReceived <= end_date)
        total_repaid = sum(
            r.AmountPaid
            for t in loan.tranches
            for r in t.repayments
            if r.DatePaid <= end_date
        )

        if total_repaid >= total_tranche_amount:
            continue

        loan_principal = 0.0
        loan_prior = 0.0

        tranches = sorted(loan.tranches, key=lambda t: t.TrancheNumber)

        for tranche in tranches:
            if tranche.DateReceived > end_date:
                continue

            repayments = [
                {
                    'DatePaid': repayment.DatePaid,
                    'Amount': float(repayment.AmountPaid)
                }
                for repayment in tranche.repayments
                if repayment.DatePaid <= end_date
            ]

            adjustments = [
                {
                    'Date': adjustment.Date,
                    'Amount': float(adjustment.Amount)
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
                "PrincipalLeft": result['PrincipalLeft'],
                "PriorInterest": result['PriorInterest'],
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




@report_bp.route('/reports/automatic-repayment-sumilation', methods=['GET'])
def simulate_repayment():
    end_date_str = request.args.get('end_date')
    selected_loan_number = request.args.get('loan_number', type=int)

    REPAYMENT_LIMIT = 500000
    MIN_SPLIT = 50000
    schedule = []

    all_loans = Loan.query.options(
        db.joinedload(Loan.tranches),
        db.joinedload(Loan.repayments),
        db.joinedload(Loan.adjustments),
        db.joinedload(Loan.project)
    ).order_by(Loan.LoanNumber).all()

    unrepaid_loans = [
        loan for loan in all_loans
        if round(sum(r.AmountPaid for r in loan.repayments), 2)
        < round(sum(t.Amount for t in loan.tranches), 2)
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

    unpaid_tranches = []
    for t in loan.tranches:
        tranche_repaid = sum(r.AmountPaid for r in loan.repayments if r.TrancheNumber == t.TrancheNumber)
        if round(tranche_repaid, 2) < round(t.Amount, 2):
            unpaid_tranches.append(t)

    unpaid_tranches.sort(key=lambda t: t.DateReceived)

    all_adjustments = [{'Amount': float(a.Amount), 'Date': a.Date, 'TrancheNumber': a.TrancheNumber} for a in loan.adjustments]
    real_repayments = [{'Amount': r.AmountPaid, 'DatePaid': r.DatePaid, 'TrancheNumber': r.TrancheNumber} for r in loan.repayments]

    # Simulate repayment schedule for unpaid tranches
    day_schedules = []
    remaining_tranches = unpaid_tranches.copy()
    current_day = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    dummy_repayments = []

    while remaining_tranches:
        day_principal = 0
        day_tranches = []
        for t in remaining_tranches:
            if day_principal + t.Amount <= REPAYMENT_LIMIT:
                day_tranches.append(t)
                day_principal += t.Amount
            elif day_principal >= REPAYMENT_LIMIT - MIN_SPLIT:
                break

        for t in day_tranches:
            remaining_tranches.remove(t)
            dummy_repayments.append({
                'Amount': t.Amount,
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


    interest_map = {}
    for tranche in loan.tranches:
        tranche_repayments = [r for r in all_repayments if r['TrancheNumber'] == tranche.TrancheNumber]
        tranche_adjustments = [a for a in all_adjustments if a['TrancheNumber'] == tranche.TrancheNumber]
        result = calculate_tranche_interest(
            tranche,
            loan.InterestRate,
            loan.Capitalization,
            final_end_date,
            repayments=tranche_repayments,
            adjustments=tranche_adjustments
        )
        interest_map[tranche.TrancheNumber] = result


    for tn, res in interest_map.items():
        prior = round(res['PriorInterest'], 2)
        yearly = round(res['YearlyInterest'], 2)
        total = prior + yearly

    total_interest = sum(i['PriorInterest'] + i['YearlyInterest'] for i in interest_map.values())
    tax_on_interest = math.floor(total_interest * 0.19)
    interest_to_lender = round(total_interest - tax_on_interest, 2)

    # Fit interest into last day if needed
    while True:
        last_day = day_schedules[-1]
        total_last_day = last_day['principal_sum'] + interest_to_lender
        if total_last_day <= REPAYMENT_LIMIT:
            break
        if not last_day['tranches']:
            break

        smallest_tranche = min(last_day['tranches'], key=lambda t: t.Amount)
        last_day['tranches'].remove(smallest_tranche)
        last_day['principal_sum'] -= smallest_tranche.Amount

        # Update dummy repayment date for this tranche
        for r in dummy_repayments:
            if r['TrancheNumber'] == smallest_tranche.TrancheNumber and r['DatePaid'] == last_day['date']:
                r['DatePaid'] = last_day['date'] + timedelta(days=1)

        next_day_date = last_day['date'] + timedelta(days=1)
        if len(day_schedules) > 1 and day_schedules[-1]['date'] == next_day_date:
            next_day = day_schedules[-1]
        else:
            next_day = {'date': next_day_date, 'tranches': [], 'principal_sum': 0}
            day_schedules.append(next_day)

        next_day['tranches'].append(smallest_tranche)
        next_day['principal_sum'] += smallest_tranche.Amount

        all_repayments = real_repayments + dummy_repayments


        final_end_date = max(r['DatePaid'] for r in all_repayments)
        interest_map = {}
        for tranche in loan.tranches:
            tranche_repayments = [r for r in all_repayments if r['TrancheNumber'] == tranche.TrancheNumber]
            tranche_adjustments = [a for a in all_adjustments if a['TrancheNumber'] == tranche.TrancheNumber]
            result = calculate_tranche_interest(
                tranche,
                loan.InterestRate,
                loan.Capitalization,
                final_end_date,
                repayments=tranche_repayments,
                adjustments=tranche_adjustments
            )
            interest_map[tranche.TrancheNumber] = result


        for tn, res in interest_map.items():
            prior = round(res['PriorInterest'], 2)
            yearly = round(res['YearlyInterest'], 2)
            total = prior + yearly


        total_interest = sum(i['PriorInterest'] + i['YearlyInterest'] for i in interest_map.values())
        tax_on_interest = math.floor(total_interest * 0.19)
        interest_to_lender = round(total_interest - tax_on_interest, 2)

    schedule = []
    for i, day in enumerate(day_schedules):
        is_last_day = (i == len(day_schedules) - 1)
        for tranche in day['tranches']:
            principal = tranche.Amount
            interest = interest_to_lender if (is_last_day and tranche == day['tranches'][-1]) else 0
            schedule.append({
                'date': day['date'],
                'LoanNumber': loan.LoanNumber,
                'TrancheNumber': tranche.TrancheNumber,
                'DateReceived': tranche.DateReceived,
                'Principal': round(principal, 2),
                'Interest': round(interest, 2),
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






@report_bp.route('/reports/manual-repayment-simulation', methods=['GET', 'POST'])
def simulate_repayment_custom():
    all_loans = Loan.query.options(
        db.joinedload(Loan.tranches),
        db.joinedload(Loan.repayments),
        db.joinedload(Loan.adjustments),
        db.joinedload(Loan.project)
    ).order_by(Loan.LoanNumber).all()

    unrepaid_loans = [
        loan for loan in all_loans
        if round(sum(r.AmountPaid for r in loan.repayments), 2)
        < round(sum(t.Amount for t in loan.tranches), 2)
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
                r.AmountPaid for r in selected_loan.repayments if r.TrancheNumber == t.TrancheNumber
            )
            if round(tranche_repaid, 2) < round(t.Amount, 2):
                amount_left = round(t.Amount - tranche_repaid, 2)
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
            total_interest = 0

            for tranche in sorted_tranches:
                tranche_repayments = [
                    r for r in selected_loan.repayments if r.TrancheNumber == tranche.TrancheNumber
                ]
                all_repayments = [{'Amount': r.AmountPaid, 'DatePaid': r.DatePaid} for r in tranche_repayments]

                repaid_amount = sum(r['Amount'] for r in all_repayments)
                if round(repaid_amount, 2) < round(tranche.Amount, 2):
                    dummy_amount = round(tranche.Amount - repaid_amount, 2)
                    repayment_date = repayment_dates.get(tranche.TrancheNumber)
                    if repayment_date:
                        all_repayments.append({'Amount': dummy_amount, 'DatePaid': repayment_date})

                tranche_adjustments = [
                    a for a in selected_loan.adjustments if a.TrancheNumber == tranche.TrancheNumber
                ]
                all_adjustments = [{'Amount': float(a.Amount), 'Date': a.Date} for a in tranche_adjustments]

                result = calculate_tranche_interest(
                    tranche,
                    selected_loan.InterestRate,
                    selected_loan.Capitalization,
                    final_repayment_date,  # Use max of all form dates
                    repayments=all_repayments,
                    adjustments=all_adjustments
                )

                prior = result['PriorInterest']
                current = result['YearlyInterest']
                final_interest = round(prior + current, 2)


                total_interest += final_interest

            tax_on_interest = math.floor(total_interest * 0.19)
            interest_to_lender = round(total_interest - tax_on_interest, 2)

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