from typing import Sequence, Optional, Literal, Tuple, List, Iterable
from sqlalchemy.sql import ColumnElement
from .models import Project, Tranche, Loan, Repayment, Adjustment
from . import db
from datetime import datetime, date
from sqlalchemy import func, cast, Numeric, not_
from sqlalchemy.exc import SQLAlchemyError
from decimal import Decimal, InvalidOperation
from sqlalchemy.orm import Query
from decimal import ROUND_HALF_UP
from markupsafe import Markup
from flask import jsonify
from collections import defaultdict



SortDir = Literal["asc", "desc"]

NBSP_NARROW = "\u202f"


# ///////////////////// Helper functions \\\\\\\\\\\\\\\\\\\\\\\\\\

# // Date parsing
def parse_iso_date(date_str: str) -> Optional[date]:
    """Parse 'YYYY-MM-DD' into a date or return None if invalid/empty."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None

# // Money conversion
def money_from_db(x) -> Decimal:
    """Convert DB numeric/float to Decimal safely."""
    if x is None:
        return Decimal("0")
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))

# // String to Decimal conversion
def to_decimal(s: Optional[str], *, places: Optional[int] = None) -> Decimal:
    if s is None or s == "":
        raise InvalidOperation("empty decimal")
    d = Decimal(s.strip())
    if places is not None:
        q = Decimal(10) ** -places
        d = d.quantize(q)
    return d

# // Checkbox parsing
def parse_checkbox(value: Optional[str]) -> bool:
    """
    HTML checkboxes send 'on' (or any non-empty string) when checked, and None when not.
    Never use bool(value) on strings like 'false' because it becomes True.
    """
    return value is not None

# // Money rounding
def round_money(x: Decimal, places: int = 2) -> Decimal:

    return Decimal(x).quantize(Decimal(10) ** -places, rounding=ROUND_HALF_UP)

# // Number formatting
def format_number_pl(value, places: int = 2, currency: bool = False) -> Markup:
    """
    Render Decimal-like value as Polish-formatted number:
    12 345 678,90  or  12 345 678,90 zł
    Uses thin NBSP as thousands separator; returns Markup to keep NBSPs intact.
    """
    d = round_money(Decimal(str(value)), places)
    neg = d < 0
    q = -d if neg else d

    int_part, frac_part = f"{q:.{places}f}".split(".")
    # group thousands
    parts = []
    while int_part:
        parts.append(int_part[-3:])
        int_part = int_part[:-3]
    grouped = NBSP_NARROW.join(reversed(parts))  # e.g., 12 345 678

    s = f"{grouped},{frac_part}" if places > 0 else grouped
    if currency:
        s = f"{s} zł"
    if neg:
        s = f"-{s}"
    return Markup(s)





# ///////////////////// Project management \\\\\\\\\\\\\\\\\\\\\\\\\\

# // All projects with status 'In Progress', with ascending or descending sorting
def get_in_progress_projects(order_by: ColumnElement = Project.ProjectID, ascending: bool = True):
    q = Project.query.filter_by(Status="In Progress")
    q = q.order_by(order_by.asc() if ascending else order_by.desc())
    return q.all()

# // Project names still In Progress
def in_progress_project_names() -> list[str]:
    """List of ProjectName values for projects still In Progress."""
    rows = get_in_progress_projects(ascending=True)
    return [p.ProjectName for p in rows]

# // Projects filtered by various criteria
def get_projects_filtered(
    statuses: Optional[Sequence[str]] = None,
    start_date_from: Optional[str] = None,  # 'YYYY-MM-DD' like other pages
    start_date_to: Optional[str] = None,
    end_date_from: Optional[str] = None,
    end_date_to: Optional[str] = None,
    order_by: Optional[ColumnElement] = None,
    direction: SortDir = "desc",            # newest first for main table
):
    """
    Return projects filtered by statuses and StartDate/EndDate ranges.
    Date filter style matches /tranches and /adjustments routes (string compare on Date columns).
    """
    q = Project.query

    if statuses:
        q = q.filter(Project.Status.in_(list(statuses)))

    # StartDate range
    if start_date_from:
        q = q.filter(Project.StartDate >= start_date_from)
    if start_date_to:
        q = q.filter(Project.StartDate <= start_date_to)

    # EndDate range (EndDate can be NULL; comparisons will exclude NULLs automatically)
    if end_date_from:
        q = q.filter(Project.EndDate >= end_date_from)
    if end_date_to:
        q = q.filter(Project.EndDate <= end_date_to)

    col = order_by or Project.ProjectID
    q = q.order_by(col.desc() if direction == "desc" else col.asc())
    return q.all()

# // Project finalization
def update_project_status_and_end_date(
    project_id: int | str,
    new_status: str,
    end_date: date,
) -> Tuple[bool, str]:
    """
    Update a project's Status and EndDate.
    Returns (success, message). Rolls back on error.
    """
    # Defensive cast (handles form strings)
    try:
        pid = int(project_id)
    except (TypeError, ValueError):
        return False, "Invalid project id."

    project = Project.query.get(pid)
    if not project:
        return False, "Project not found."

    # Optionally: validate new_status against allowed values if you have them.
    # Example:
    # allowed = {"In Progress", "On Hold", "Completed", "Cancelled"}
    # if new_status not in allowed:
    #     return False, f"Invalid status: {new_status}"

    project.Status = new_status
    project.EndDate = end_date

    try:
        db.session.commit()
        return True, f"Project '{project.ProjectName}' updated successfully."
    except Exception as e:
        db.session.rollback()
        return False, f"Failed to update project: {e}"

# // Project name normalization
def normalize_project_name(name: str) -> str:
    """
    Strip, collapse inner spaces, and capitalize like your current behavior:
    first letter uppercase, rest lowercase.
    """
    if not name:
        return ""
    cleaned = " ".join(name.strip().split())
    return cleaned.capitalize()

# // Project name existence check
def project_name_exists(name: str) -> bool:
    """
    Case-insensitive uniqueness check.
    """
    return (
        db.session.query(Project.ProjectID)
        .filter(func.lower(Project.ProjectName) == func.lower(name))
        .first()
        is not None
    )

# // Project creation
def create_project_record(project_name: str, start_date_str: Optional[str]) -> Tuple[bool, str]:
    """
    Validates and creates a new Project with Status='In Progress'.
    start_date_str should be 'YYYY-MM-DD' or None/''.
    Returns (success, message). Rolls back on error.
    """
    name = normalize_project_name(project_name)
    if not name:
        return False, "Project name is required."

    if len(name) > 100:
        return False, "Project name is too long! Maximum length is 100 characters."

    if project_name_exists(name):
        return False, "A project with this name already exists."

    start_date: Optional[date] = parse_iso_date(start_date_str)
    if start_date_str and not start_date:
        return False, "Invalid start date format."

    # Start date cannot be in the future (compare as dates)
    if start_date and start_date > date.today():
        return False, "Start date cannot be in the future."

    new_project = Project(
        ProjectName=name,
        StartDate=start_date,   # works if your column is DATE; if it's DateTime, we can cast to datetime
        Status="In Progress",
    )

    try:
        db.session.add(new_project)
        db.session.commit()
        return True, "Project created successfully!"
    except Exception as e:
        db.session.rollback()
        return False, f"Failed to create project: {e}"

# // Project deletion
def delete_project_by_id(project_id: int, *, protect_if_related: bool = True) -> Tuple[bool, str]:
    """
    Delete a project by id.
    - If `protect_if_related` is True, refuse deletion when related rows exist (e.g., loans/tranches),
      to avoid integrity errors or orphan records.
    Returns (success, message). Rolls back on error.
    """
    project = Project.query.get(project_id)
    if not project:
        return False, "Project not found."

    # OPTIONAL: Safety check — only if your Project has backrefs/relationships.
    # Adjust attribute names if your models differ (e.g., project.loans).
    if protect_if_related:
        try:
            has_any_relations = False
            # Example checks; comment out or adapt to your actual relationships:
            if hasattr(project, "loans") and project.loans:
                has_any_relations = True
            if hasattr(project, "tranches") and project.tranches:
                has_any_relations = True
            if hasattr(project, "repayments") and project.repayments:
                has_any_relations = True

            if has_any_relations:
                return False, "Cannot delete: project has related records. Archive it or remove dependents first."
        except Exception:
            # If relationship attributes don’t exist, ignore and proceed.
            pass

    try:
        db.session.delete(project)
        db.session.commit()
        return True, "Project deleted successfully."
    except SQLAlchemyError as e:
        db.session.rollback()
        return False, f"Error occurred while deleting the project: {e}"

# // Distinct project names
def distinct_project_names() -> list[str]:
    """
    Unique project names, newest first by latest ProjectID.
    Portable across databases.
    """
    rows = (
        db.session.query(
            Project.ProjectName,
            func.max(Project.ProjectID).label("latest_id"),
        )
        .group_by(Project.ProjectName)
        .order_by(func.max(Project.ProjectID).desc())
        .all()
    )
    return [r[0] for r in rows]

# // Loan dropdown (Loan X - Project Y - XYZ)
def loan_dropdown_options() -> Tuple[list[str], list[dict]]:
    """
    Build dropdown options for loans that are not fully repaid.
    Returns:
      - loans_dropdown: ["123 - ProjectX - TypeA", ...]
      - loans: [{"LoanNumber": ..., "ProjectName": ..., "ProjectType": ...}, ...]
    """

    total_tranche_amount = (
        db.session.query(
            Tranche.LoanNumber,
            func.coalesce(func.sum(cast(Tranche.Amount, Numeric(18, 2))), Decimal("0")).label("TotalLoanAmount"),
        )
        .group_by(Tranche.LoanNumber)
        .subquery()
    )

    total_repaid_amount = (
        db.session.query(
            Repayment.LoanNumber,
            func.coalesce(func.sum(cast(Repayment.AmountPaid, Numeric(18, 2))), Decimal("0")).label("TotalRepaid"),
        )
        .group_by(Repayment.LoanNumber)
        .subquery()
    )

    loans_query = (
        db.session.query(
            Loan.LoanNumber,
            Project.ProjectName,
            Loan.ProjectType,
        )
        .join(Project, Loan.ProjectID == Project.ProjectID)
        .outerjoin(total_tranche_amount, Loan.LoanNumber == total_tranche_amount.c.LoanNumber)
        .outerjoin(total_repaid_amount, Loan.LoanNumber == total_repaid_amount.c.LoanNumber)
        .filter(
            not_(
                (func.coalesce(total_repaid_amount.c.TotalRepaid, Decimal("0")) == func.coalesce(total_tranche_amount.c.TotalLoanAmount, Decimal("0")))
                & (func.coalesce(total_repaid_amount.c.TotalRepaid, Decimal("0")) > 0)
            )
        )
        .all()
    )

    loans_dropdown = [f"{l.LoanNumber} - {l.ProjectName} - {l.ProjectType}" for l in loans_query]
    loans = [{"LoanNumber": l.LoanNumber, "ProjectName": l.ProjectName, "ProjectType": l.ProjectType} for l in loans_query]

    return loans_dropdown, loans








# //////////////////// Loan management \\\\\\\\\\\\\\\\\\\\\\\\\\

# // Tranche totals subquery
def tranche_totals_subq():
    """
    Sum of tranche amounts per LoanNumber.
    Uses CAST to Numeric so Postgres returns DECIMAL, not float.
    """
    return (
        db.session.query(
            Tranche.LoanNumber.label("LoanNumber"),
            func.coalesce(
                func.sum(cast(Tranche.Amount, Numeric(18, 2))),
                Decimal("0"),
            ).label("TotalReceived"),
        )
        .group_by(Tranche.LoanNumber)
        .subquery()
    )

# // Repayment totals subquerry
def repayment_totals_subq():
    """
    Sum of repayments per LoanNumber.
    Uses CAST to Numeric so Postgres returns DECIMAL, not float.
    """
    return (
        db.session.query(
            Repayment.LoanNumber.label("LoanNumber"),
            func.coalesce(
                func.sum(cast(Repayment.AmountPaid, Numeric(18, 2))),
                Decimal("0"),
            ).label("TotalRepaid"),
        )
        .group_by(Repayment.LoanNumber)
        .subquery()
    )

# // Loan querry
def get_loans_with_totals(
    selected_projects: Optional[Sequence[str]] = None,
    selected_project_types: Optional[Sequence[str]] = None,
    start_date_from: Optional[str] = None,  # 'YYYY-MM-DD'
    start_date_to: Optional[str] = None,    # 'YYYY-MM-DD'
    status_filter: Optional[str] = None,    # "fully_repaid" | "not_repaid" | None
    order_desc: bool = False,
):
    """
    Return rows: (Loan, ProjectName, fully_repaid: bool) with totals computed.
    All monetary aggregation is DECIMAL via CAST.
    """
    t_subq = tranche_totals_subq()
    r_subq = repayment_totals_subq()

    q: Query = (
        db.session.query(
            Loan,
            Project.ProjectName,
            t_subq.c.TotalReceived,
            r_subq.c.TotalRepaid,
        )
        .join(Project, Loan.ProjectID == Project.ProjectID)
        .outerjoin(t_subq, t_subq.c.LoanNumber == Loan.LoanNumber)
        .outerjoin(r_subq, r_subq.c.LoanNumber == Loan.LoanNumber)
    )

    # Filters
    if selected_projects:
        q = q.filter(Project.ProjectName.in_(list(selected_projects)))
    if selected_project_types:
        q = q.filter(Loan.ProjectType.in_(list(selected_project_types)))
    if start_date_from:
        q = q.filter(Loan.StartDate >= start_date_from)
    if start_date_to:
        q = q.filter(Loan.StartDate <= start_date_to)

    # Status filter applied in SQL using DECIMAL equality/inequality
    if status_filter == "fully_repaid":
        q = q.filter(
            func.coalesce(t_subq.c.TotalReceived, Decimal("0"))
            == func.coalesce(r_subq.c.TotalRepaid, Decimal("0"))
        )
    elif status_filter == "not_repaid":
        q = q.filter(
            func.coalesce(t_subq.c.TotalReceived, Decimal("0"))
            != func.coalesce(r_subq.c.TotalRepaid, Decimal("0"))
        )

    q = q.order_by(Loan.LoanNumber.desc() if order_desc else Loan.LoanNumber.asc())

    # Map to the tuple your template expects: (loan, project_name, fully_repaid)
    rows = q.all()
    loans_data: List[Tuple[Loan, str, bool]] = []
    for loan, project_name, total_received, total_repaid in rows:
        rec = money_from_db(total_received)
        rep = money_from_db(total_repaid)
        fully_repaid = (rec == rep) and (rec > Decimal("0"))
        loans_data.append((loan, project_name, fully_repaid))

    return loans_data

# // Increment loan number
def next_loan_number() -> int:
    """Get next sequential LoanNumber (based on current max)."""
    max_num = db.session.query(func.max(Loan.LoanNumber)).scalar()
    return (int(max_num) + 1) if max_num is not None else 1

# // Loan creation
def create_loan_record(
    *,
    project_name: str,
    total_amount_str: str,
    interest_rate_str: str,
    capitalization_str: Optional[str],
    project_type: Optional[str],
    start_date_str: Optional[str],
) -> Tuple[bool, str]:
    """
    Validate and create a Loan using Decimal for amounts/rates.
    Returns (ok, message). Handles commit/rollback.
    """

    # Project lookup
    project = db.session.query(Project).filter_by(ProjectName=project_name).first()
    if not project:
        return False, "Selected project not found."

    # Parse inputs safely (Decimally)
    try:
        total_amount = to_decimal(total_amount_str, places=2)  # money
    except InvalidOperation:
        return False, "Invalid total amount."

    try:
        # interest is a fraction (e.g., 0.12 for 12%)
        interest_rate = to_decimal(interest_rate_str)  # don't quantize; keep user precision
    except InvalidOperation:
        return False, "Invalid interest rate."

    capitalization = parse_checkbox(capitalization_str)
    start_date = parse_iso_date(start_date_str)

    # Validate
    errors = []
    if interest_rate <= Decimal("0") or interest_rate >= Decimal("1"):
        errors.append("Interest rate must be between 0 and 1 (exclusive).")
    if start_date and start_date > date.today():
        errors.append("Start date cannot be in the future.")
    if errors:
        return False, " ".join(errors)

    # Generate LoanNumber
    loan_number = next_loan_number()

    # Create
    new_loan = Loan(
        LoanNumber=loan_number,
        ProjectID=project.ProjectID,
        TotalAmount=total_amount,     # Decimal (models may still be Float; migration recommended)
        InterestRate=interest_rate,   # Decimal fraction (e.g., 0.12)
        Capitalization=capitalization,
        ProjectType=project_type,
        StartDate=start_date,
    )

    try:
        db.session.add(new_loan)
        db.session.commit()
        return True, "Loan created successfully!"
    except Exception as e:
        db.session.rollback()
        return False, f"Error creating loan: {e}"

# // Loan deletion
def delete_loan_by_id(loan_id: int, *, protect_if_related: bool = True) -> Tuple[bool, str]:
    """
    Delete a loan by id.
    - If `protect_if_related` is True, refuse deletion when related rows exist (e.g., tranches/repayments),
      to avoid integrity errors or orphan records.
    Returns (success, message).
    """
    loan = Loan.query.get(loan_id)
    if not loan:
        return False, "Loan not found."

    if protect_if_related:
        try:
            has_any_relations = False
            if hasattr(loan, "tranches") and loan.tranches:
                has_any_relations = True
            if hasattr(loan, "repayments") and loan.repayments:
                has_any_relations = True
            if has_any_relations:
                return False, "Cannot delete: loan has related tranches or repayments. Archive it instead."
        except Exception:
            # If relationships not set up, skip
            pass

    try:
        db.session.delete(loan)
        db.session.commit()
        return True, "Loan deleted successfully."
    except SQLAlchemyError as e:
        db.session.rollback()
        return False, f"Error occurred while deleting the loan: {e}"

# // Unpaid loans dropdown
def unpaid_loans_dropdown() -> list[dict]:
    """
    Return loans that are not fully repaid, for use in repayment dropdowns.
    Each dict has LoanNumber, ProjectName, ProjectType.
    """

    total_tranche_amount = (
        db.session.query(
            Tranche.LoanNumber,
            func.coalesce(func.sum(cast(Tranche.Amount, Numeric(18, 2))), Decimal("0")).label("TotalLoanAmount"),
        )
        .group_by(Tranche.LoanNumber)
        .subquery()
    )

    total_repaid_amount = (
        db.session.query(
            Repayment.LoanNumber,
            func.coalesce(func.sum(cast(Repayment.AmountPaid, Numeric(18, 2))), Decimal("0")).label("TotalRepaid"),
        )
        .group_by(Repayment.LoanNumber)
        .subquery()
    )

    loans = (
        db.session.query(
            Loan.LoanNumber,
            Project.ProjectName,
            Loan.ProjectType,
        )
        .join(Project, Loan.ProjectID == Project.ProjectID)
        .outerjoin(total_tranche_amount, Loan.LoanNumber == total_tranche_amount.c.LoanNumber)
        .outerjoin(total_repaid_amount, Loan.LoanNumber == total_repaid_amount.c.LoanNumber)
        .filter(
            not_(
                (func.coalesce(total_repaid_amount.c.TotalRepaid, Decimal("0"))
                 == func.coalesce(total_tranche_amount.c.TotalLoanAmount, Decimal("0")))
                & (func.coalesce(total_repaid_amount.c.TotalRepaid, Decimal("0")) > 0)
            )
        )
        .all()
    )

    return [
        {"LoanNumber": l.LoanNumber, "ProjectName": l.ProjectName, "ProjectType": l.ProjectType}
        for l in loans
    ]

# // Loans dropdown (unpaid or all)
def loans_dropdown_unpaid_or_all(unpaid_only: bool = True) -> list[dict]:
    """
    Dropdown data for loans.
    - unpaid_only=True → loans not fully repaid (reuses unpaid_loans_dropdown()).
    - unpaid_only=False → all loans.
    """
    if unpaid_only:
        # reuse existing helper from repayments/tranches
        return unpaid_loans_dropdown()

    rows = (
        db.session.query(Loan.LoanNumber, Project.ProjectName, Loan.ProjectType)
        .join(Project, Loan.ProjectID == Project.ProjectID)
        .order_by(Loan.LoanNumber.asc())
        .all()
    )
    return [
        {"LoanNumber": r.LoanNumber, "ProjectName": r.ProjectName, "ProjectType": r.ProjectType}
        for r in rows
    ]



# ///////////////////// Tranche management \\\\\\\\\\\\\\\\\\\\\\\\\


# // Tranches querry with filters
def get_tranches_filtered(
    selected_loan_numbers: Optional[Sequence[str]] = None,
    status_filter: Optional[str] = None,  # "repaid" | "ongoing" | None
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """
    Return tranches with repayment totals and status labels,
    ordered by DateReceived descending (latest first).
    """

    repayment_subq = (
        db.session.query(
            Repayment.LoanNumber,
            Repayment.TrancheNumber,
            func.coalesce(func.sum(cast(Repayment.AmountPaid, Numeric(18, 2))), Decimal("0")).label("TotalRepaid"),
        )
        .group_by(Repayment.LoanNumber, Repayment.TrancheNumber)
        .subquery()
    )

    q = (
        db.session.query(
            Tranche.LoanNumber,
            Tranche.TrancheNumber,
            Tranche.Amount,
            Tranche.DateReceived,
            func.coalesce(repayment_subq.c.TotalRepaid, Decimal("0")).label("TotalRepaid"),
        )
        .outerjoin(
            repayment_subq,
            (Tranche.LoanNumber == repayment_subq.c.LoanNumber)
            & (Tranche.TrancheNumber == repayment_subq.c.TrancheNumber),
        )
    )

    if selected_loan_numbers:
        q = q.filter(Tranche.LoanNumber.in_(selected_loan_numbers))

    if status_filter in ("repaid", "ongoing"):
        q = q.group_by(
            Tranche.LoanNumber,
            Tranche.TrancheNumber,
            Tranche.Amount,
            Tranche.DateReceived,
            repayment_subq.c.TotalRepaid,
        )
        if status_filter == "repaid":
            q = q.having(func.coalesce(repayment_subq.c.TotalRepaid, Decimal("0")) == Tranche.Amount)
        elif status_filter == "ongoing":
            q = q.having(func.coalesce(repayment_subq.c.TotalRepaid, Decimal("0")) < Tranche.Amount)

    if date_from:
        q = q.filter(Tranche.DateReceived >= date_from)
    if date_to:
        q = q.filter(Tranche.DateReceived <= date_to)

    # 👇 Ensure newest tranches show first
    q = q.order_by(Tranche.DateReceived.desc())

    rows = q.all()

    tranches_data = []
    for loan_number, tranche_number, amount, date_received, total_repaid in rows:
        status = "Repaid" if money_from_db(amount) == money_from_db(total_repaid) else "Ongoing"
        tranches_data.append(
            {
                "LoanNumber": loan_number,
                "TrancheNumber": tranche_number,
                "Amount": money_from_db(amount),
                "DateReceived": date_received,
                "Status": status,
            }
        )

    return tranches_data

# // Tranche number increment
def next_tranche_number(loan_number: int) -> int:
    """Get next tranche number for a given loan."""
    last_tranche = (
        db.session.query(Tranche)
        .filter_by(LoanNumber=loan_number)
        .order_by(Tranche.TrancheNumber.desc())
        .first()
    )
    return 1 if not last_tranche else last_tranche.TrancheNumber + 1

# // Tranche creation
def create_tranche_record(
    *,
    loan_number: str | int,
    tranche_date_str: str,
    amount_str: str,
) -> Tuple[bool, str]:
    """
    Validate and create a new Tranche for a Loan.
    Returns (ok, message). Handles commit/rollback.
    """

    # Loan lookup
    try:
        loan_number = int(loan_number)
    except (TypeError, ValueError):
        return False, "Invalid loan number."

    loan = Loan.query.get(loan_number)
    if not loan:
        return False, "Loan not found."

    # Date validation
    tranche_date = parse_iso_date(tranche_date_str)
    if not tranche_date:
        return False, "Tranche date is required and must be YYYY-MM-DD."
    if tranche_date > date.today():
        return False, "Tranche date cannot be in the future."

    # Amount validation
    try:
        amount = to_decimal(amount_str, places=2)
    except InvalidOperation:
        return False, "Invalid amount."
    if amount <= Decimal("0"):
        return False, "Amount must be positive."

    # (Optional) total received so far (could be used for checks/limits)
    total_received = (
        db.session.query(func.coalesce(func.sum(cast(Tranche.Amount, Numeric(18, 2))), Decimal("0")))
        .filter(Tranche.LoanNumber == loan.LoanNumber)
        .scalar()
    )
    # Example: if you want to enforce "cannot exceed TotalAmount", uncomment:
    # if total_received + amount > loan.TotalAmount:
    #     return False, "Tranche exceeds total loan amount."

    # Next TrancheNumber
    tranche_number = next_tranche_number(loan.LoanNumber)

    # Create
    new_tranche = Tranche(
        LoanNumber=loan.LoanNumber,
        TrancheNumber=tranche_number,
        DateReceived=tranche_date,
        Amount=amount,
    )

    try:
        db.session.add(new_tranche)
        db.session.commit()
        return True, "Tranche added successfully."
    except Exception as e:
        db.session.rollback()
        return False, f"Error while saving tranche: {e}"

# // Tranche deletion
def delete_tranche_by_id(loan_number: int, tranche_number: int) -> Tuple[bool, str]:
    """
    Delete a tranche given LoanNumber + TrancheNumber.
    Returns (success, message). Rolls back on error.
    """
    tranche = Tranche.query.filter_by(
        LoanNumber=loan_number, TrancheNumber=tranche_number
    ).first()
    if not tranche:
        return False, "Tranche not found."

    try:
        db.session.delete(tranche)
        db.session.commit()
        return True, "Tranche deleted successfully."
    except Exception as e:
        db.session.rollback()
        return False, f"Error occurred while deleting the tranche: {e}"

# // Get tranches for loan
def get_tranches_for_loan_all(loan_number: int) -> list[dict]:
    """
    Return ALL tranches for a loan (not filtered by repayment status),
    sorted by TrancheNumber ASC. Amount returned as a string with 2 decimals.
    """
    amount_num = cast(Tranche.Amount, Numeric(18, 2))

    rows = (
        db.session.query(
            Tranche.TrancheNumber,
            amount_num.label("Amount"),
            Tranche.DateReceived,
        )
        .filter(Tranche.LoanNumber == loan_number)
        .order_by(Tranche.TrancheNumber.asc())
        .all()
    )

    tranches = []
    for tn, amt, drec in rows:
        amt_dec = money_from_db(amt)
        tranches.append({
            "TrancheNumber": tn,
            "Amount": str(amt_dec.quantize(Decimal("0.01"))),  # JSON-safe string
            "DateReceived": drec.isoformat() if drec else None,
        })
    return tranches







# ///////////////////// Repayment Functions \\\\\\\\\\\\\\\\\\\\\\\\\\\\


# // Repayments querry
def get_repayments_filtered(
    selected_loan_numbers: Optional[Sequence[str]] = None,
    selected_statuses: Optional[Sequence[str]] = None,  # ["Full Repayment", "Partial Repayment"]
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """
    Fetch repayments joined with their tranche amounts, apply filters,
    and compute repayment status.
    Returns a list of dicts, ordered by DatePaid DESC (latest first).
    """

    q = (
        db.session.query(
            Repayment.LoanNumber,
            Repayment.TrancheNumber,
            Repayment.DatePaid,
            Repayment.AmountPaid,
            Tranche.Amount.label("TrancheAmount"),
        )
        .outerjoin(
            Tranche,
            (Repayment.LoanNumber == Tranche.LoanNumber)
            & (Repayment.TrancheNumber == Tranche.TrancheNumber),
        )
    )

    if selected_loan_numbers:
        q = q.filter(Repayment.LoanNumber.in_(selected_loan_numbers))
    if date_from:
        q = q.filter(Repayment.DatePaid >= date_from)
    if date_to:
        q = q.filter(Repayment.DatePaid <= date_to)

    # 👇 newest repayments first
    q = q.order_by(Repayment.DatePaid.desc())

    rows = q.all()

    repayment_data = []
    for r in rows:
        tranche_amount = money_from_db(r.TrancheAmount)
        paid = money_from_db(r.AmountPaid)

        if tranche_amount > 0:
            status = "Full Repayment" if paid >= tranche_amount else "Partial Repayment"
        else:
            status = "Unknown"

        if selected_statuses and status not in selected_statuses:
            continue

        repayment_data.append(
            {
                "LoanNumber": r.LoanNumber,
                "TrancheNumber": r.TrancheNumber,
                "DatePaid": r.DatePaid,
                "AmountPaid": paid,
                "Status": status,
            }
        )

    return repayment_data

# // Create repayment
def create_repayment_record(
    *,
    loan_number: str | int,
    tranche_number: str | int,
    date_paid_str: str,
    amount_paid_str: str,
) -> Tuple[bool, str]:
    """
    Validate and create a Repayment for a given Loan/Tranche.
    Returns (ok, message). Handles commit/rollback.
    """

    # Loan/tranche lookup
    try:
        loan_number = int(loan_number)
        tranche_number = int(tranche_number)
    except (TypeError, ValueError):
        return False, "Invalid loan or tranche number."

    tranche = Tranche.query.filter_by(LoanNumber=loan_number, TrancheNumber=tranche_number).first()
    if not tranche:
        return False, "Invalid tranche selected."

    # Date parsing
    date_paid = parse_iso_date(date_paid_str)
    if not date_paid:
        return False, "Repayment date is required and must be YYYY-MM-DD."
    if date_paid < tranche.DateReceived:
        return False, "Repayment date cannot be before the tranche date."

    # Amount parsing
    try:
        amount_paid = to_decimal(amount_paid_str, places=2)
    except InvalidOperation:
        return False, "Invalid repayment amount."
    if amount_paid <= Decimal("0"):
        return False, "Repayment amount must be positive."

    # Total already repaid for this tranche
    total_repaid = (
        db.session.query(func.coalesce(func.sum(cast(Repayment.AmountPaid, Numeric(18, 2))), Decimal("0")))
        .filter_by(LoanNumber=loan_number, TrancheNumber=tranche_number)
        .scalar()
    )
    total_repaid = money_from_db(total_repaid)

    remaining_amount = money_from_db(tranche.Amount) - total_repaid
    if amount_paid > remaining_amount:
        return False, f"Repayment exceeds remaining amount ({format_number_pl(remaining_amount)}) for this tranche."

    # Create repayment
    new_repayment = Repayment(
        LoanNumber=loan_number,
        TrancheNumber=tranche_number,
        DatePaid=date_paid,
        AmountPaid=amount_paid,
    )

    try:
        db.session.add(new_repayment)
        db.session.commit()
        return True, "Repayment added successfully!"
    except Exception as e:
        db.session.rollback()
        return False, f"Error saving repayment: {e}"

# // Delete repayment
def delete_repayment_by_id(
    loan_number: int,
    tranche_number: int,
    date_str: str,
) -> Tuple[bool, str]:
    """
    Delete a repayment by (LoanNumber, TrancheNumber, DatePaid).
    Returns (success, message). Rolls back on error.
    """

    date_paid = parse_iso_date(date_str)
    if not date_paid:
        return False, "Invalid repayment date."

    repayment = Repayment.query.filter_by(
        LoanNumber=loan_number,
        TrancheNumber=tranche_number,
        DatePaid=date_paid,
    ).first()

    if not repayment:
        return False, "Repayment not found."

    try:
        db.session.delete(repayment)
        db.session.commit()
        return True, "Repayment deleted successfully."
    except Exception as e:
        db.session.rollback()
        return False, f"Error deleting repayment: {e}"

# // Get unpaid tranches
def get_unpaid_tranches_for_loan(loan_number: int) -> list[dict]:
    """
    For a given loan, return all tranches that are not fully repaid,
    with their remaining amount as a string with 2 decimals (JSON-safe).
    """

    amount_num = cast(Tranche.Amount, Numeric(18, 2))

    tranches = (
        db.session.query(
            Tranche.TrancheNumber,
            amount_num.label("TrancheAmount"),
            func.coalesce(func.sum(cast(Repayment.AmountPaid, Numeric(18, 2))), Decimal("0")).label("TotalRepayment"),
        )
        .outerjoin(
            Repayment,
            (Tranche.LoanNumber == Repayment.LoanNumber)
            & (Tranche.TrancheNumber == Repayment.TrancheNumber),
        )
        .filter(Tranche.LoanNumber == loan_number)
        .group_by(Tranche.TrancheNumber, amount_num)
        .having(
            func.coalesce(func.sum(cast(Repayment.AmountPaid, Numeric(18, 2))), Decimal("0"))
            < amount_num
        )
        .order_by(Tranche.TrancheNumber.asc())  # or Tranche.DateReceived.asc() if you prefer
        .all()
    )

    tranche_list = []
    for t in tranches:
        amount = money_from_db(t.TrancheAmount)
        repaid = money_from_db(t.TotalRepayment)
        remaining = amount - repaid
        tranche_list.append(
            {
                "TrancheNumber": t.TrancheNumber,
                # send as string to avoid JS float issues; 2-decimal quantize
                "RemainingAmount": str(remaining.quantize(Decimal("0.01"))),
            }
        )

    return tranche_list




# //////////////////////// Adjustment functions \\\\\\\\\\\\\\\\\\\\\\\\\


# // Adjustments querry with filters
def get_adjustments_filtered(
    loan_numbers: Optional[Sequence[int]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """
    Return Adjustment rows filtered by loan numbers and date range,
    newest first by Adjustment.Date.
    """
    q = db.session.query(Adjustment).order_by(Adjustment.Date.desc())

    if loan_numbers:
        q = q.filter(Adjustment.LoanNumber.in_(loan_numbers))
    if date_from:
        q = q.filter(Adjustment.Date >= date_from)
    if date_to:
        q = q.filter(Adjustment.Date <= date_to)

    return q.all()

# // Delete adjustment
def delete_adjustment_by_id(adjustment_id: int) -> tuple[bool, str]:
    """
    Delete an Adjustment by id.
    Returns (success, message). Rolls back on error.
    """
    adjustment = Adjustment.query.get(adjustment_id)
    if not adjustment:
        return False, "Adjustment not found."

    try:
        db.session.delete(adjustment)
        db.session.commit()
        return True, "Adjustment deleted successfully."
    except SQLAlchemyError as e:
        db.session.rollback()
        return False, f"Error deleting adjustment: {e}"

# // Create adjustment
def create_adjustment_record(
    *,
    loan_number: str | int,
    tranche_number: str | int,
    date_str: str,
    amount_str: str,
    description: str | None = "",
) -> tuple[bool, str]:
    """
    Validate and create an Adjustment using Decimal for amount.
    Returns (ok, message). Handles commit/rollback.
    Notes:
      - Allows negative amounts (e.g., corrections). Blocks zero.
      - Ensures (LoanNumber, TrancheNumber) exists.
    """

    # Parse IDs
    try:
        loan_num = int(loan_number)
        tranche_num = int(tranche_number)
    except (TypeError, ValueError):
        return False, "Invalid loan or tranche number."

    # Check tranche exists for the loan
    tranche = (
        db.session.query(Tranche)
        .filter_by(LoanNumber=loan_num, TrancheNumber=tranche_num)
        .first()
    )
    if not tranche:
        return False, "Selected tranche not found for this loan."

    # Parse date (YYYY-MM-DD)
    adj_date = parse_iso_date(date_str)
    if not adj_date:
        return False, "Adjustment date is required and must be YYYY-MM-DD."
    if adj_date > date.today():
        return False, "Adjustment date cannot be in the future."

    # Parse amount (Decimal, 2 places)
    try:
        amount = to_decimal(amount_str, places=2)
    except InvalidOperation:
        return False, "Invalid adjustment amount."

    # Business rule: allow negative (corrections) but not zero
    if amount == Decimal("0"):
        return False, "Adjustment amount cannot be zero."

    # Create
    new_adj = Adjustment(
        LoanNumber=loan_num,
        TrancheNumber=tranche_num,
        Date=adj_date,
        Amount=amount,
        Description=(description or "").strip(),
    )

    try:
        db.session.add(new_adj)
        db.session.commit()
        return True, "Adjustment added successfully."
    except Exception as e:
        db.session.rollback()
        return False, f"Error adding adjustment: {e}"




# /////////////////////// Reporting functions \\\\\\\\\\\\\\\\\\\\\\\\\\\\



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

    # 🔑 Ensure interest_rate is always Decimal
    interest_rate = money_from_db(interest_rate)

    start_date = tranche.DateReceived
    original_principal = money_from_db(tranche.Amount)
    remaining_principal = original_principal
    capitalized_interest = Decimal("0")
    prior_interest = Decimal("0")
    current_year_interest = Decimal("0")

    current_year = end_date.year
    start_year = start_date.year

    # Organize repayments and adjustments by year
    repayments_by_year = defaultdict(list)
    for r in repayments:
        repayments_by_year[r['DatePaid'].year].append({
            "DatePaid": r['DatePaid'],
            "Amount": money_from_db(r['Amount'])
        })

    adjustments_by_year = defaultdict(Decimal)
    for a in adjustments:
        adjustments_by_year[a['Date'].year] += money_from_db(a['Amount'])

    for year in range(start_year, current_year + 1):
        yearly_interest = Decimal("0")
        year_start = max(start_date, date(year - 1, 12, 31))
        year_end = min(end_date, date(year, 12, 31))

        # Get repayments within the year and sort by date
        year_repayments = sorted(
            repayments_by_year.get(year, []),
            key=lambda r: r["DatePaid"]
        )

        # Split year into periods based on repayments
        period_start = year_start
        for repayment in year_repayments:
            period_end = min(repayment["DatePaid"], year_end)
            if period_end > period_start and remaining_principal > 0:
                days = (period_end - period_start).days
                fraction = Decimal(days) / Decimal(366)  # keep 366 as in your original
                yearly_interest += remaining_principal * interest_rate * fraction
                period_start = period_end
            # Apply repayment
            remaining_principal -= repayment["Amount"]
            if remaining_principal < 0:
                remaining_principal = Decimal("0")

        # Final period to year_end
        if remaining_principal > 0 and period_start < year_end:
            days = (year_end - period_start).days
            fraction = Decimal(days) / Decimal(366)
            yearly_interest += remaining_principal * interest_rate * fraction

        # Interest on capitalized interest
        cap_days = (min(year_end, end_date) - year_start).days
        cap_fraction = Decimal(cap_days) / Decimal(366)
        if capitalization:
            yearly_interest += capitalized_interest * interest_rate * cap_fraction
            capitalized_interest += yearly_interest  # Only update if capitalization is on

        # Add adjustments at the end of the year to yearly interest
        yearly_adjustment = adjustments_by_year.get(year, Decimal("0"))
        yearly_interest += yearly_adjustment

        # Track prior/current year interest
        if year < current_year:
            prior_interest += yearly_interest
        elif year == current_year:
            current_year_interest += yearly_interest

    return {
        "PrincipalLeft": round_money(remaining_principal, 2),
        "PriorInterest": round_money(prior_interest, 2),
        "YearlyInterest": round_money(current_year_interest, 2),
    }













