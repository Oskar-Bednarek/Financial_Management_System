from .main import main
from .projects import projects_bp
from .export import export_bp
from .loans import loans_bp
from .tranches import tranches_bp
from .repayments import repayments_bp
from .adjustments import adjustments_bp
from .yearly_report import report_bp

blueprints = [main, export_bp, projects_bp, loans_bp, tranches_bp, repayments_bp, adjustments_bp, report_bp
]
