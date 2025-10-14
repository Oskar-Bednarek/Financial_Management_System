# 💼 KeriM Financial Management System

A custom-built, Flask-based financial management system designed to track projects, loans, tranches, repayments, and generate detailed financial reports with advanced automation capabilities.

---

## 🚀 Features

### Core Financial Management
- **Project & Loan Tracking**: Complete lifecycle management with status tracking
- **Tranche Management**: Individual loan disbursement tracking with dates and amounts
- **Repayment Processing**: Payment allocation with automatic interest calculations
- **Adjustment System**: Manual corrections and adjustments to financial calculations
- **Interest Calculations**: Complex daily accrual with capitalization support (366-day year)

### Advanced Reporting
- **Annual Reports**: Yearly interest reports with capitalization tracking
- **Daily Reports**: Custom date range reports with detailed breakdowns
- **Loan Reports**: Loan-specific interest calculations and summaries
- **Repayment Simulation**: Advanced simulation with custom payment scenarios
- **Export Options**: Excel/CSV export for all reports

### AI-Powered Workflow Automation (NEW in v2.0)
- **Automated Protocol Generation**: AI-powered tenant change protocol workflow
- **Claude AI Integration**: Intelligent analysis of Excel price estimates
- **Google Drive Integration**: Automated document management and organization
- **Smart Summaries**: Automatic extraction of costs and change categories
- **PDF Generation**: Automated protocol and estimate PDF creation

### Polish Business Support
- **Polish Currency Formatting**: Proper number formatting (12 345,67 zł)
- **Polish Date Formats**: ISO date handling throughout
- **Localized UI**: Interface elements in Polish

### Technical Features
- **Custom UI**: Built with Tailwind CSS
- **PostgreSQL Database**: Robust data storage with SQLAlchemy ORM
- **Blueprint Architecture**: Modular route organization
- **Centralized Business Logic**: Maintainable helper function library
- **Environment Variables**: Secure credential management
- **Optional Packaging**: Can be packaged as standalone `.exe` (no Python required for end users)

---

## 📁 Project Structure

```
Financial_Management_System/
├── app/
│   ├── __init__.py           # Flask app factory with Jinja2 filters
│   ├── models.py             # SQLAlchemy models (Project, Loan, Tranche, Repayment, Adjustment)
│   ├── functions.py          # Centralized business logic and helpers
│   ├── routes/
│   │   ├── __init__.py       # Blueprint registration
│   │   ├── main.py           # Home dashboard
│   │   ├── projects.py       # Project management
│   │   ├── loans.py          # Loan tracking
│   │   ├── tranches.py       # Tranche disbursements
│   │   ├── repayments.py     # Payment processing
│   │   ├── adjustments.py    # Manual adjustments
│   │   ├── report_annual.py  # Yearly reports
│   │   ├── report_daily.py   # Custom date reports
│   │   ├── report_loan.py    # Loan-specific reports
│   │   ├── repay_sim.py      # Repayment simulation
│   │   ├── workflows.py      # AI workflow automation
│   │   └── export.py         # Data export
│   ├── workflows/
│   │   └── workflow_nodes.py # Google Drive/Sheets integration
│   ├── templates/            # Jinja2 templates
│   │   ├── base.html
│   │   ├── partials/
│   │   └── workflows.html    # NEW: Workflow UI
│   └── static/
│       ├── logo.png          # Add your logo here
│       └── logo2.png         # Add your logo here (for watermarks)
├── config.py                 # Database and Flask config (create from example)
├── config_example.py         # Configuration template
├── run.py                    # Application entry point
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (create from example below)
├── .gitignore
├── CHANGELOG.md
├── CLAUDE.md                 # AI assistant instructions
└── README.md
```

---

## 🛠️ Setup Instructions

Follow these steps to run the project locally.

---

### ✅ Step 1: Clone the repository

```bash
git clone https://github.com/Oskar-Bednarek/Financial_Management_System.git
cd Financial_Management_System
```

---

### ✅ Step 2: Create a virtual environment (recommended)

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

---

### ✅ Step 3: Install the required packages

```bash
pip install -r requirements.txt
```

This includes:
- Flask and SQLAlchemy for the web framework
- PostgreSQL drivers (psycopg2)
- Google API clients for Drive/Sheets integration
- Anthropic SDK for Claude AI
- pandas, openpyxl for data export
- And many more scientific computing libraries

---

### ✅ Step 4: Configure the database

Copy the example configuration file and edit it:

```bash
cp config_example.py config.py
```

Then open `config.py` and set your:

- `SQLALCHEMY_DATABASE_URI` - Your PostgreSQL connection string (e.g., Neon, local PostgreSQL)
- `SECRET_KEY` - Any random string for Flask session security

Example:
```python
SQLALCHEMY_DATABASE_URI = "postgresql://user:password@host:5432/database"
SECRET_KEY = "your-secret-key-here"
```

---

### ✅ Step 5: Set up environment variables (for workflows)

Create a `.env` file in the project root for sensitive credentials:

```bash
# Google OAuth2 Credentials (for workflow automation)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REFRESH_TOKEN=your-refresh-token

# Anthropic API (for Claude AI)
ANTHROPIC_API_KEY=sk-ant-...

# Optional: Other API keys
CONVERTAPI_SECRET=your-convertapi-secret
```

**Note**: Workflow features require these credentials. Core financial features work without them.

**How to get Google OAuth credentials**:
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project and enable Drive + Sheets APIs
3. Create OAuth2 credentials
4. Use the OAuth playground to get a refresh token

---

### ✅ Step 6: Add your logos

Add 2 logo files to these paths:

- `app/static/logo.png` - Main logo visible in the sidebar
- `app/static/logo2.png` - Logo used for document watermarks

You may use the placeholders already included if you just want to test.

---

### ✅ Step 7: Run the application

```bash
python run.py
```

Your default web browser will open automatically at:

**[http://127.0.0.1:5000/Kerim_Financial_Management_System](http://127.0.0.1:5000/Kerim_Financial_Management_System)**

The application auto-opens your browser after a 1.5-second delay.

---

## 🧊 Building a Windows Executable (Optional)

To generate a single `.exe` for end users (no Python required):

1. Install PyInstaller:

```bash
pip install pyinstaller
```

2. Build the executable:

```bash
pyinstaller --noconfirm --onefile --add-data "app;app" --add-data "tailwind.config.js;." run.py
```

3. The `.exe` will appear in the `dist/` folder.

You can distribute this to others without requiring Python or manual setup.

---

## 🎯 Key Modules Explained

### `app/functions.py` - Centralized Business Logic
This module contains all reusable business logic extracted from routes:

- **Financial calculations**: Interest computation, capitalization, repayment allocation
- **Data validation**: Date parsing, decimal handling, checkbox parsing
- **Polish formatting**: `format_number_pl()` for currency display
- **Database queries**: Filtered queries with sorting and pagination
- **CRUD operations**: Project, loan, tranche, repayment, adjustment management

### `app/routes/workflows.py` - AI Automation
Handles the automated tenant change protocol workflow:

1. Receives form input (project name, unit number, contract date, Excel file)
2. Looks up project data from master Google Sheet
3. Uploads Excel file to Google Drive and converts to Sheets
4. Calls Claude AI API to analyze price estimate
5. Creates and fills protocol template in Google Sheets
6. Exports both protocol and estimate to PDF
7. Organizes all files in Drive folders

### `app/workflows/workflow_nodes.py` - Google Integration
Helper functions for Google services:

- `get_google_credentials()` - OAuth2 authentication
- `get_google_services()` - Returns authenticated Drive/Sheets clients
- `create_drive_folder()` - Creates folders in Drive
- `upload_excel_to_drive()` - Uploads files
- `convert_excel_to_google_sheet()` - Converts Excel to Sheets format

---

## 🔧 Database Models

The system uses 5 core SQLAlchemy models:

1. **Project** - Main entity tracking project lifecycle
   - Fields: ProjectID, ProjectName, Status, StartDate, EndDate
   - Status: "In Progress", "On Hold", "Completed", "Cancelled"

2. **Loan** - Individual loans linked to projects
   - Fields: LoanID, ProjectID, InterestRate, TaxRate, Capitalization
   - Supports multiple loans per project

3. **Tranche** - Loan disbursements
   - Fields: TrancheID, LoanID, Amount, TrancheDate
   - Tracks when and how much was disbursed

4. **Repayment** - Payments against tranches
   - Fields: RepaymentID, TrancheID, Amount, RepaymentDate
   - Automatically allocated to reduce principal

5. **Adjustment** - Manual corrections
   - Fields: AdjustmentID, TrancheID, Amount, AdjustmentDate, Description
   - Allows manual interest/principal adjustments

---

## 🤖 AI Workflow Details

The workflow automation uses Claude 3.5 Haiku to intelligently analyze price estimates:

**Input**: Excel file with cost breakdown
**AI Processing**:
- Analyzes all sheets for cost data
- Extracts total cost (removes spaces: `4 600,20` → `4600,20`)
- Summarizes changes in max 5 bullet points (60 chars each)
- Groups related changes (e.g., "Wentylacja, ogrodzenie, sufity")
- Removes brand names, uses generic categories

**Output**: JSON with `total_cost`, `summary_points`, `sheet_name`

**Protocol Generation**:
- Fills template with project data, AI summary, costs
- Calculates adjusted price based on unit area (150m² threshold)
- Generates price difference formula
- Exports to PDF with proper Polish formatting

---

## 📊 Reporting Features

### Annual Report (`/report_annual`)
- Yearly interest calculations with capitalization
- Breakdown by project and loan
- Total interest accrued and capitalized
- Export to Excel with formatting

### Daily Report (`/report_daily`)
- Custom date range selection
- Detailed tranche-by-tranche breakdown
- Principal remaining, interest accrued
- Repayment impact tracking

### Loan Report (`/report_loan`)
- Loan-specific interest summary
- Multi-year calculations
- Tranche-level details
- Adjustment tracking

### Repayment Simulation
- "What-if" scenarios for different payment amounts
- Impact on interest calculations
- Multiple simulation comparisons
- Visual representation of payoff schedules

---

## 🔐 Security Notes

- **Environment Variables**: All API keys and credentials stored in `.env` (not committed)
- **Database Credentials**: PostgreSQL connection string in `config.py` (not committed)
- **OAuth Tokens**: Google refresh tokens stored in `.env`
- **Session Security**: Flask SECRET_KEY required for secure sessions
- **`.gitignore`**: Excludes all sensitive files (`.env`, `config.py`, token files)

---

## 📝 Version History

- **v2.0.0** (2025-01-14) - Major refactoring, AI workflows, modular reports, -1,200 lines
- **v1.0.0** (2025-01-01) - Initial release with core financial features

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

---

## 📝 License

This project is proprietary to KeriM or personal use unless otherwise specified.

---

## 🤝 Contributing

If you'd like to collaborate or extend the project:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📞 Support

For issues or questions:
- Open an issue on [GitHub](https://github.com/Oskar-Bednarek/Financial_Management_System/issues)
- Check [CLAUDE.md](CLAUDE.md) for AI assistant guidance
- Review [CHANGELOG.md](CHANGELOG.md) for recent updates
