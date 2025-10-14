# Changelog

All notable changes to this project will be documented in this file.


## [Unreleased]
- Features, bug fixes, and improvements that are planned or in progress.

## [2.0.0] - 2025-01-14

### Major Refactoring & New Features
This release includes significant architectural improvements with code consolidation and powerful automation features.

### Added

#### **AI-Powered Workflow Automation System**
- **Automated Tenant Change Protocol Workflow**:
  - AI analysis of Excel price estimates using Claude 3.5 Haiku API
  - Automatic cost extraction and change summary generation (up to 5 points)
  - Intelligent categorization of changes without brand names
  - Google Drive integration for document management
  - Automated Google Sheets protocol template population
  - PDF generation and upload for both protocols and estimates
  - Smart protocol numbering based on existing folder structure
- **New `/workflows` Route**: Web interface for submitting and managing workflows
- **Google Services Integration Module** (`app/workflows/workflow_nodes.py`):
  - OAuth2 authentication for Google Drive and Sheets APIs
  - Drive folder creation and file organization
  - Excel to Google Sheets conversion
  - PDF export and upload functionality
  - Master sheet data lookup

#### **Centralized Business Logic Module** (`app/functions.py`)
Created comprehensive helper library (~500+ lines) consolidating logic from multiple routes:
- **Financial Operations**: Interest calculations, capitalization, repayment processing
- **Data Validation & Parsing**: Date parsing, decimal conversion, checkbox handling
- **Polish Formatting**: Currency and number formatting with proper NBSP separators
- **Database Operations**: Reusable CRUD functions with transaction management
- **Query Builders**: Filtered queries for projects, tranches, loans with sorting
- **Reporting Utilities**: Shared report generation logic

#### **Modular Reporting System**
Replaced monolithic reporting with specialized modules:
- `report_annual.py` - Yearly interest reports with capitalization tracking
- `report_daily.py` - Custom date range reports with detailed breakdowns
- `report_loan.py` - Loan-specific interest calculations and summaries
- `repay_sim.py` - Advanced repayment simulation with custom scenarios

#### **New Dependencies**
- `anthropic==0.40.0` - Claude AI API integration
- `google-auth==2.23.4` - Google OAuth2 authentication
- `google-auth-oauthlib==1.1.0` - OAuth2 flow handling
- `google-auth-httplib2==0.1.1` - HTTP transport for Google APIs
- `google-api-python-client==2.108.0` - Google Drive and Sheets clients
- `python-dotenv` - Environment variable management

#### **Enhanced Features**
- **Jinja2 Template Filters**: `pl_number` and `pl_currency` filters for consistent Polish formatting
- **Environment Variables**: `.env` file support for API keys and credentials
- **Extended Date Filtering**: Project filtering with start/end date range inputs
- **Improved Templates**: Updated UI with better Polish currency display across all views

### Changed

#### **Major Code Refactoring** (Net: -1,203 lines)
- **Extracted Business Logic**: Moved ~1,200 lines from routes to `app/functions.py`
- **Route Simplification**:
  - `projects.py`: -130 lines (extracted to helper functions)
  - `loans.py`: -155 lines (extracted to helper functions)
  - `tranches.py`: -226 lines (extracted to helper functions)
  - `repayments.py`: -194 lines (extracted to helper functions)
  - `adjustments.py`: -91 lines (extracted to helper functions)
- **Improved Code Organization**: Routes now focus solely on HTTP handling
- **Type Safety**: Added comprehensive type hints to helper functions

#### **Template Updates**
- `adjustments.html`: Improved formatting and UI (124 line changes)
- `repayments.html`: Enhanced layout and display (102 line changes)
- `partials/sidebar.html`: Added workflows navigation link
- Updated currency formatting across all report templates
- Better date input styling and validation

#### **Configuration**
- `app/__init__.py`: Added `.env` loading and Jinja2 filter registration
- `app/routes/__init__.py`: Updated blueprint imports for new modular structure
- `.gitignore`: Added entries for `.env`, credentials, and Google OAuth tokens
- `run.py`: Minor adjustments for environment-based config

### Removed
- `app/routes/yearly_report.py` - Replaced by modular reporting system
- Duplicate helper functions scattered across route files
- Redundant validation logic
- Inline business logic from route handlers

### Fixed
- Improved decimal precision in all financial calculations
- Better error messages with proper Polish formatting
- Enhanced date parsing with edge case handling
- Consistent transaction rollback on database errors
- Fixed number formatting with correct thin non-breaking spaces (U+202F)

### Technical Improvements
- **Maintainability**: Centralized logic reduces update overhead
- **Testability**: Pure functions easier to unit test
- **Performance**: Reduced code duplication and optimized queries
- **Scalability**: Modular architecture supports feature expansion
- **Security**: Sensitive credentials moved to environment variables

---

## [1.0.0] - 2025-01-01
### Added
- Initial release with core functionalities:
  - Project management (create, view, delete)
  - Loan, tranche, repayment, and adjustment views
  - Interest calculation and reporting
  - Filtering and export of data (Excel/CSV)



