from .main import main
from .projects import projects_bp
from .export import export_bp
from .loans import loans_bp
from .tranches import tranches_bp
from .repayments import repayments_bp
from .adjustments import adjustments_bp
from .report_annual import report_annual_bp
from .report_daily import report_daily_bp
from .report_loan import report_loan_bp
from .repay_sim import repayment_sim_bp
from .workflows import workflows_bp


blueprints = [main, export_bp, projects_bp, loans_bp, tranches_bp, repayments_bp, adjustments_bp, report_annual_bp, 
            report_daily_bp, report_loan_bp, repayment_sim_bp, workflows_bp]
