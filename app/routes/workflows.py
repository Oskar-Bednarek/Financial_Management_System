# app/routes/workflow.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
import os
import json
import tempfile
from pathlib import Path
from datetime import date
from ..workflows.workflow_nodes import (
    create_drive_folder, 
    upload_excel_to_drive, 
    convert_excel_to_google_sheet,
    get_google_services
)
from googleapiclient.http import MediaFileUpload
import anthropic

workflows_bp = Blueprint("workflows", __name__)

# ===== WORKFLOW CONSTANTS - Extracted from n8n JSON =====

# Master Google Sheets Document (contains project data)
MASTER_SHEET_ID = "1lV9N_6L1cvsb6No0fDIyC0-WL5SXoVGSxztKuUCO5Iw"
MASTER_SHEET_NAME_ID = 1848300859  # "Dane" sheet
MASTER_SHEET_NAME = "Dane"

# Protocol Template Document (to be copied for each protocol)
TEMPLATE_PROTOCOL_ID = "1w73mdLPg8wd6yStLT09ZM4kYiJC5a6_6DqON1YX9EOI"

# AI Model Configuration
AI_MODEL = "claude-3-5-haiku-20241022"

# Credential IDs (for reference - actual credentials come from .env)
# GOOGLE_DRIVE_CRED_ID = "sW3pA8ZpbhRzWpg8"  # Google Drive KeriM
# GOOGLE_SHEETS_CRED_ID = "GNJE8Ip6DRcxmLGV"  # Google Sheets KeriM 
# ANTHROPIC_CRED_ID = "JKzpnxGVYFtrK96g"  # Anthropic account
# CONVERTAPI_CRED_ID = "uVN5d0cTLRR5bPUJ"  # ConvertAPI account

# Protocol Template Cell Mappings (adjusted after manual row deletion)
PROTOCOL_CELLS = {
    'title': {'row': 4, 'col': 'B'},          # Protocol title with number
    'investment': {'row': 6, 'col': 'D'},     # Project name
    'unit': {'row': 8, 'col': 'D'},           # Unit number
    'clients': {'row': 10, 'col': 'D'},       # Client names
    'summary_1': {'row': 13, 'col': 'C'},     # AI summary point 1
    'summary_2': {'row': 14, 'col': 'C'},     # AI summary point 2
    'summary_3': {'row': 15, 'col': 'C'},     # AI summary point 3
    'summary_4': {'row': 16, 'col': 'C'},     # AI summary point 4
    'summary_5': {'row': 17, 'col': 'C'},     # AI summary point 5
    'price_calculation': {'row': 21, 'col': 'F'},  # Price formula
    'price_difference': {'row': 22, 'col': 'F'},   # Price difference
    'execution_date': {'row': 26, 'col': 'F'},     # Contract execution date
    'payment_terms': {'row': 31, 'col': 'F'},      # Payment terms
}

# AI Analysis System Prompt
AI_SYSTEM_PROMPT = """Jesteś analitykiem wycen zmian lokatorskich. Otrzymujesz plik Google Sheets zawierający szczegóły zmian zleconych przez klienta.

Twoje zadania:
1. Oblicz całkowity koszt wszystkich zmian.
2. Streść zakres zmian w maksymalnie 5 punktach (może być mniej, jeśli zmian jest mniej).
3. Podaj nazwe Arkusza ktory zawiera dane.

Zasady:
- Analizuj arkusz, uzuj do tego udostepnionego narzedzia oraz podanych ID pliku oraz Nazwy arkusza.
- Traktuj wszystkie zmiany jako jedną całość. Łącz powiązane zmiany w jeden logiczny punkt – nawet jeśli dotyczą różnych elementów (np. „Wentylacja, ogrodzenie, sufity").
- Każdy punkt streszczenia może zawierać **kilka nazw kategorii zmian** oddzielonych przecinkami, maksymalnie 60 znaków.
- Unikaj nazw firm i marek – używaj tylko ogólnych nazw (np. „Drzwi wejściowe", „Instalacje elektryczne", „Kuchnia").
- Nie podawaj kosztów jednostkowych – tylko **łączny koszt wszystkich zmian**.
- Upewnij sie ze w total cost nie zawierasz spacji(4 600,20 - W TAKI SPOSOB NIE ROB, ZAMIAST TEGO ZROB 4600,20)

**Zwróć odpowiedź wyłącznie w formacie JSON:**

```json
{
  "total_cost": "4300,20",
  "summary_points": [
    "Wentylacja, ogrodzenie, sufity",
    "Drzwi wejściowe, instalacja elektryczna"
  ],
  "sheet_name": "Sheet_1"
}
```"""

def get_project_data(project_name, unit_number):
    """
    Look up project data from master Google Sheet.
    Returns dict with project info or None if not found.
    """
    try:
        _, sheets_service = get_google_services()
        
        # Get all rows from the master sheet
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=MASTER_SHEET_ID,
            range=f"{MASTER_SHEET_NAME}!A:Z"
        ).execute()
        
        values = result.get('values', [])
        if not values:
            return None
            
        # Find header row and get column indices
        headers = values[0] if values else []
        investment_col = None
        unit_col = None
        clients_col = None
        folder_id_col = None
        area_col = None
        
        for i, header in enumerate(headers):
            if 'Inwestycja' in header:
                investment_col = i
            elif 'Numer Lokalu' in header:
                unit_col = i
            elif 'Klienci' in header:
                clients_col = i
            elif 'ID folderu' in header:
                folder_id_col = i
            elif 'Metraż' in header:
                area_col = i
        
        # Search for matching project
        for row in values[1:]:  # Skip header
            if (len(row) > max(investment_col or 0, unit_col or 0) and
                row[investment_col] == project_name and
                row[unit_col] == unit_number):
                
                return {
                    'project_name': row[investment_col] if investment_col and len(row) > investment_col else project_name,
                    'unit_number': row[unit_col] if unit_col and len(row) > unit_col else unit_number,
                    'clients': row[clients_col] if clients_col and len(row) > clients_col else '',
                    'folder_id': row[folder_id_col] if folder_id_col and len(row) > folder_id_col else '',
                    'area': row[area_col] if area_col and len(row) > area_col else ''
                }
        
        return None
        
    except Exception as e:
        print(f"Error getting project data: {e}")
        return None

def get_next_protocol_number(parent_folder_id):
    """
    Mimic the original n8n workflow logic:
    1. Search files and folders in project folder  
    2. Filter out items with no ID
    3. Extract all IDs and count unique IDs
    4. Protocol number = distinctIdCount + 1
    """
    try:
        drive_service, _ = get_google_services()
        
        # Search for files and folders in the parent folder (mimicking n8n "Search files and folders")
        # Exclude trashed files to avoid counting deleted items
        results = drive_service.files().list(
            q=f"'{parent_folder_id}' in parents and trashed=false",
            fields="files(id, name)"
        ).execute()
        
        items = results.get('files', [])
        
        # Debug: Print all items found
        print(f"DEBUG - All items in project folder ({parent_folder_id}):")
        for item in items:
            print(f"  - {item.get('name', 'Unknown')} (ID: {item.get('id', 'None')})")
        
        # Filter out items with no id or empty id (mimicking n8n JavaScript)
        filtered_items = [item for item in items if item.get('id') is not None and item.get('id') != '']
        
        # Extract all IDs
        ids = [item.get('id') for item in filtered_items]
        
        # Create a Set to ensure uniqueness (mimicking n8n logic)
        unique_ids = set(ids)
        distinct_id_count = len(unique_ids)
        
        print(f"DEBUG - Filtered items: {len(filtered_items)}")
        print(f"DEBUG - Unique IDs count (distinctIdCount): {distinct_id_count}")
        
        # Protocol number = distinctIdCount + 1 (exact n8n logic)
        next_number = distinct_id_count + 1
        print(f"DEBUG - Next protocol number will be: {next_number}")
        
        return next_number
        
    except Exception as e:
        print(f"Error getting protocol number: {e}")
        return 1

def analyze_price_estimate_with_ai(sheet_id):
    """
    Use Claude API to analyze the price estimate sheet.
    Returns dict with total_cost, summary_points, and sheet_name.
    """
    try:
        # Get sheet metadata to find sheet names
        _, sheets_service = get_google_services()
        
        # Get sheet info
        sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        sheets = sheet_metadata.get('sheets', [])
        
        if not sheets:
            return None
            
        # Use first sheet
        first_sheet = sheets[0]['properties']['title']
        
        # Get sheet data for analysis context
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"{first_sheet}!A1:Z1000"
        ).execute()
        
        values = result.get('values', [])
        if not values:
            return None
            
        # Convert to text for AI analysis
        sheet_text = ""
        for row in values[:100]:  # Limit to first 100 rows
            sheet_text += "\t".join([str(cell) for cell in row]) + "\n"
        
        # Initialize Claude client
        client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        
        # Create AI prompt
        user_prompt = f"""Proszę przeanalizuj udostępniony plik i zwróć wynik zgodnie z instrukcjami.

Dane do analizy:
ID pliku: {sheet_id}
Nazwa arkusza: {first_sheet}

Zawartość arkusza (pierwsze 100 wierszy):
{sheet_text}
"""

        # Call Claude API
        response = client.messages.create(
            model=AI_MODEL,
            max_tokens=1000,
            system=AI_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        
        # Parse JSON response
        response_text = response.content[0].text
        
        # Extract JSON from response (it might be wrapped in markdown)
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            analysis_result = json.loads(json_str)
            
            # Ensure we have the required fields
            if all(key in analysis_result for key in ['total_cost', 'summary_points']):
                return analysis_result
        
        return None
        
    except Exception as e:
        print(f"Error in AI analysis: {e}")
        return None

def copy_and_fill_protocol_template(protocol_number, project_data, ai_analysis, contract_date, time_of_payment, folder_id):
    """
    Copy the protocol template and fill it with project data and AI analysis.
    Returns the new protocol document ID.
    """
    try:
        drive_service, sheets_service = get_google_services()
        
        # Step 1: Copy the template
        protocol_name = f"Protokół_zmian_lokatorskich_{protocol_number}_{project_data['project_name']}_Lokal_{project_data['unit_number']}"
        
        copied_file = drive_service.files().copy(
            fileId=TEMPLATE_PROTOCOL_ID,
            body={
                'name': protocol_name,
                'parents': [folder_id]
            }
        ).execute()
        
        protocol_id = copied_file['id']
        print(f"Copied protocol template: {protocol_id}")
        
        # Step 2: Get the first sheet name from the copied protocol
        protocol_metadata = sheets_service.spreadsheets().get(spreadsheetId=protocol_id).execute()
        protocol_sheet_name = protocol_metadata['sheets'][0]['properties']['title']
        
        # Step 3: Fill in all the data
        updates = []
        
        # Title
        title_text = f"ZLECENIE WYKONANIA ROBÓT BUDOWLANYCH PROTOKÓŁ ZMIAN LOKATORSKICH {protocol_number}"
        updates.append({
            'range': f"{protocol_sheet_name}!{PROTOCOL_CELLS['title']['col']}{PROTOCOL_CELLS['title']['row']}",
            'values': [[title_text]]
        })
        
        # Project details
        updates.append({
            'range': f"{protocol_sheet_name}!{PROTOCOL_CELLS['investment']['col']}{PROTOCOL_CELLS['investment']['row']}",
            'values': [[project_data['project_name']]]
        })
        
        updates.append({
            'range': f"{protocol_sheet_name}!{PROTOCOL_CELLS['unit']['col']}{PROTOCOL_CELLS['unit']['row']}",
            'values': [[project_data['unit_number']]]
        })
        
        updates.append({
            'range': f"{protocol_sheet_name}!{PROTOCOL_CELLS['clients']['col']}{PROTOCOL_CELLS['clients']['row']}",
            'values': [[project_data.get('clients', '')]]
        })
        
        # AI Summary points
        summary_points = ai_analysis.get('summary_points', [])
        for i in range(5):  # We have 5 summary slots
            point_text = summary_points[i] if i < len(summary_points) else ''
            updates.append({
                'range': f"{protocol_sheet_name}!{PROTOCOL_CELLS[f'summary_{i+1}']['col']}{PROTOCOL_CELLS[f'summary_{i+1}']['row']}",
                'values': [[point_text]]
            })
        
        # Price calculation (with area-based formula from n8n)
        total_cost_raw = ai_analysis.get('total_cost', '0').replace(' ', '')
        area_str = project_data.get('area', '0') or '0'
        # Handle Polish number format (comma as decimal separator)
        area = float(area_str.replace(',', '.'))
        
        # Convert total_cost to use Polish decimal format for Excel
        total_cost_polish = total_cost_raw.replace('.', ',') if '.' in total_cost_raw else total_cost_raw
        area_polish = area_str  # Keep original Polish format
        
        if area <= 150:
            price_formula = f"={total_cost_polish}"
        else:
            price_formula = f"={total_cost_polish}/{area_polish}*150"
            
        updates.append({
            'range': f"{protocol_sheet_name}!{PROTOCOL_CELLS['price_calculation']['col']}{PROTOCOL_CELLS['price_calculation']['row']}",
            'values': [[price_formula]]
        })
        
        # Price difference calculation
        price_diff_formula = f"={total_cost_polish}-{PROTOCOL_CELLS['price_calculation']['col']}{PROTOCOL_CELLS['price_calculation']['row']}"
        updates.append({
            'range': f"{protocol_sheet_name}!{PROTOCOL_CELLS['price_difference']['col']}{PROTOCOL_CELLS['price_difference']['row']}",
            'values': [[price_diff_formula]]
        })
        
        # Dates and terms
        updates.append({
            'range': f"{protocol_sheet_name}!{PROTOCOL_CELLS['execution_date']['col']}{PROTOCOL_CELLS['execution_date']['row']}",
            'values': [[contract_date]]
        })
        
        payment_terms = time_of_payment or "3 dni od podpisania niniejszego protokołu"
        updates.append({
            'range': f"{protocol_sheet_name}!{PROTOCOL_CELLS['payment_terms']['col']}{PROTOCOL_CELLS['payment_terms']['row']}",
            'values': [[payment_terms]]
        })
        
        # Batch update all cells
        body = {
            'valueInputOption': 'USER_ENTERED',
            'data': updates
        }
        
        sheets_service.spreadsheets().values().batchUpdate(
            spreadsheetId=protocol_id,
            body=body
        ).execute()
        
        print(f"Protocol filled successfully: {protocol_id}")
        return protocol_id
        
    except Exception as e:
        print(f"Error copying/filling protocol: {e}")
        return None

def rename_and_cleanup_files(excel_file_id, sheet_id, protocol_number, project_name, unit_number):
    """
    Rename the Google Sheets file and delete the original Excel file.
    """
    try:
        drive_service, _ = get_google_services()
        
        # Rename the Google Sheets file
        sheets_name = f"Wycena_zmian_lokatorskich_{protocol_number}_{project_name}_Lokal_{unit_number}"
        drive_service.files().update(
            fileId=sheet_id,
            body={'name': sheets_name}
        ).execute()
        print(f"Renamed sheets file to: {sheets_name}")
        
        # Delete the original Excel file
        drive_service.files().delete(fileId=excel_file_id).execute()
        print(f"Deleted original Excel file: {excel_file_id}")
        
        return True
        
    except Exception as e:
        print(f"Error renaming/cleaning files: {e}")
        return False

def export_to_pdf_and_upload(protocol_id, sheet_id, folder_id, protocol_number, project_name, unit_number):
    """
    Export both protocol and price estimate to PDF and upload to Drive.
    Returns tuple: (protocol_pdf_id, estimate_pdf_id)
    """
    try:
        drive_service, _ = get_google_services()
        
        # Export protocol to PDF
        protocol_pdf_response = drive_service.files().export(
            fileId=protocol_id,
            mimeType='application/pdf'
        ).execute()
        
        # Export price estimate to PDF  
        estimate_pdf_response = drive_service.files().export(
            fileId=sheet_id,
            mimeType='application/pdf'
        ).execute()
        
        # Upload protocol PDF
        protocol_pdf_name = f"Protokół_zmian_lokatorskich_{protocol_number}_{project_name}_Lokal_{unit_number}.pdf"
        protocol_media = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        try:
            protocol_media.write(protocol_pdf_response)
            protocol_media.close()
            
            protocol_pdf_metadata = {
                'name': protocol_pdf_name,
                'parents': [folder_id]
            }
            
            protocol_pdf_media = MediaFileUpload(protocol_media.name, mimetype='application/pdf')
            
            protocol_pdf_file = drive_service.files().create(
                body=protocol_pdf_metadata,
                media_body=protocol_pdf_media,
                fields='id'
            ).execute()
            
            protocol_pdf_id = protocol_pdf_file.get('id')
            print(f"Uploaded protocol PDF: {protocol_pdf_id}")
            
        finally:
            try:
                os.unlink(protocol_media.name)
            except OSError:
                pass  # File might still be locked
        
        # Upload price estimate PDF
        estimate_pdf_name = f"Wycena_zmian_lokatorskich_{protocol_number}_{project_name}_Lokal_{unit_number}.pdf"
        estimate_media = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        try:
            estimate_media.write(estimate_pdf_response)
            estimate_media.close()
            
            estimate_pdf_metadata = {
                'name': estimate_pdf_name,
                'parents': [folder_id]
            }
            
            estimate_pdf_media = MediaFileUpload(estimate_media.name, mimetype='application/pdf')
            
            estimate_pdf_file = drive_service.files().create(
                body=estimate_pdf_metadata,
                media_body=estimate_pdf_media,
                fields='id'
            ).execute()
            
            estimate_pdf_id = estimate_pdf_file.get('id')
            print(f"Uploaded price estimate PDF: {estimate_pdf_id}")
            
        finally:
            try:
                os.unlink(estimate_media.name)
            except OSError:
                pass  # File might still be locked
        
        return protocol_pdf_id, estimate_pdf_id
        
    except Exception as e:
        print(f"Error exporting/uploading PDFs: {e}")
        return None, None

def run_workflow(project_name, unit_number, contract_date, time_of_payment, price_estimate_file):
    """
    Main workflow orchestration function.
    Returns tuple: (success: bool, message: str, result_data: dict)
    """
    try:
        print(f"Starting workflow for {project_name} - Unit {unit_number}")
        
        # Step 1: Get project data from master sheet
        project_data = get_project_data(project_name, unit_number)
        if not project_data:
            return False, f"Project '{project_name}' Unit '{unit_number}' not found in master sheet", {}
        
        print(f"Found project data: {project_data}")
        
        # Step 2: Get next protocol number (count existing protocol folders in main project folder)
        protocol_number = get_next_protocol_number(project_data['folder_id'])
        print(f"Protocol number: {protocol_number}")
        
        # Step 3: Create project folder
        folder_name = f"Protokół nr {protocol_number}"
        folder_id = create_drive_folder(folder_name, project_data['folder_id'])
        print(f"Created folder: {folder_id}")
        
        # Step 4: Save uploaded file temporarily and upload to Drive
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
        try:
            price_estimate_file.save(temp_file.name)
            temp_file.close()  # Close the file handle before uploading
            temp_path = Path(temp_file.name)
            
            # Upload to Drive
            excel_file_id = upload_excel_to_drive(folder_id, temp_path)
            print(f"Uploaded Excel file: {excel_file_id}")
            
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass  # File might already be deleted
        
        # Step 5: Convert Excel to Google Sheets
        sheet_id = convert_excel_to_google_sheet(excel_file_id)
        print(f"Converted to sheet: {sheet_id}")
        
        # Step 6: AI Analysis of the price estimate
        print("Starting AI analysis...")
        ai_analysis = analyze_price_estimate_with_ai(sheet_id)
        if not ai_analysis:
            return False, "Failed to analyze price estimate with AI", {}
        
        print(f"AI Analysis complete: {ai_analysis}")
        
        # Step 7: Copy protocol template and fill with data
        print("Creating and filling protocol...")
        protocol_id = copy_and_fill_protocol_template(
            protocol_number=protocol_number,
            project_data=project_data,
            ai_analysis=ai_analysis,
            contract_date=contract_date,
            time_of_payment=time_of_payment,
            folder_id=folder_id
        )
        
        if not protocol_id:
            return False, "Failed to create protocol document", {}
        
        # Step 8: Rename sheets file and cleanup Excel file
        print("Renaming files and cleaning up...")
        cleanup_success = rename_and_cleanup_files(
            excel_file_id=excel_file_id,
            sheet_id=sheet_id,
            protocol_number=protocol_number,
            project_name=project_data['project_name'],
            unit_number=project_data['unit_number']
        )
        
        if not cleanup_success:
            print("Warning: File cleanup failed, continuing with PDF export...")
        
        # Step 9: Export both documents to PDF and upload
        print("Exporting to PDF and uploading...")
        protocol_pdf_id, estimate_pdf_id = export_to_pdf_and_upload(
            protocol_id=protocol_id,
            sheet_id=sheet_id,
            folder_id=folder_id,
            protocol_number=protocol_number,
            project_name=project_data['project_name'],
            unit_number=project_data['unit_number']
        )
        
        if not protocol_pdf_id:
            return False, "Failed to export protocol to PDF", {}
        
        if not estimate_pdf_id:
            print("Warning: Failed to export price estimate to PDF, continuing...")
        
        # Step 10: Workflow completion
        print("Workflow completed successfully!")
        
        return True, f"✅ Protocol {protocol_number} completed! Generated PDF documents - AI found {len(ai_analysis.get('summary_points', []))} change categories with total cost: {ai_analysis.get('total_cost', 'N/A')}", {
            'protocol_number': protocol_number,
            'folder_id': folder_id,
            'excel_file_id': excel_file_id,
            'sheet_id': sheet_id,
            'protocol_id': protocol_id,
            'protocol_pdf_id': protocol_pdf_id,
            'estimate_pdf_id': estimate_pdf_id,
            'project_data': project_data,
            'ai_analysis': ai_analysis
        }
        
    except Exception as e:
        print(f"Workflow error: {e}")
        return False, f"Workflow failed: {str(e)}", {}

@workflows_bp.route("/workflows", methods=["GET"])
def workflow_start():
    return render_template("workflows.html")

@workflows_bp.route("/workflow/submit", methods=["POST"])
def workflow_submit():
    try:
        # Get form data matching HTML form fields
        project_name = request.form.get("project_name")
        unit_number = request.form.get("unit_number")
        contract_date = request.form.get("contract_date")
        time_of_payment = request.form.get("time_of_payment")
        price_estimate = request.files.get("price_estimate")

        # Basic validation (time_of_payment is optional)
        if not all([project_name, unit_number, contract_date, price_estimate]):
            flash("Project Name, Unit Number, Contract Date, and Price Estimate are required", "error")
            return redirect(url_for("workflows.workflow_start"))

        # Validate file type
        if price_estimate and not price_estimate.filename.endswith(('.xls', '.xlsx')):
            flash("Price estimate must be an Excel file (.xls or .xlsx)", "error")
            return redirect(url_for("workflows.workflow_start"))

        # Validate file size (10MB limit)
        if price_estimate.content_length and price_estimate.content_length > 10 * 1024 * 1024:
            flash("File size must be less than 10MB", "error")
            return redirect(url_for("workflows.workflow_start"))

        # Run the workflow
        success, message, result_data = run_workflow(
            project_name=project_name.strip(),
            unit_number=unit_number.strip(),
            contract_date=contract_date,
            time_of_payment=time_of_payment.strip(),
            price_estimate_file=price_estimate
        )

        if success:
            flash(f"✅ {message}", "success")
        else:
            flash(f"❌ {message}", "error")

        return redirect(url_for("workflows.workflow_start"))
        
    except Exception as e:
        flash(f"❌ Unexpected error: {str(e)}", "error")
        return redirect(url_for("workflows.workflow_start"))
