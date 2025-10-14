import os
from pathlib import Path
from typing import Dict, Any, List
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ---- Setup ----
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
]

def get_google_credentials():
    """
    Create OAuth credentials from environment variables.
    Uses refresh token to get valid access token.
    """
    creds = Credentials(
        token=None,  # Will be refreshed
        refresh_token=os.getenv('GOOGLE_REFRESH_TOKEN'),
        client_id=os.getenv('GOOGLE_CLIENT_ID'),
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        token_uri='https://oauth2.googleapis.com/token',
        scopes=SCOPES
    )
    
    # Refresh the token to get a valid access token
    creds.refresh(Request())
    return creds

def get_google_services():
    """Get authenticated Google Drive and Sheets services."""
    creds = get_google_credentials()
    drive_service = build("drive", "v3", credentials=creds)
    sheets_service = build("sheets", "v4", credentials=creds)
    return drive_service, sheets_service


# ---- Nodes ----

def create_drive_folder(project_name: str, parent_folder_id: str = None) -> str:
    """Create a folder in Google Drive. Returns folder ID."""
    drive_service, _ = get_google_services()
    
    file_metadata = {
        "name": project_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_folder_id:
        file_metadata["parents"] = [parent_folder_id]

    folder = drive_service.files().create(body=file_metadata, fields="id").execute()
    return folder["id"]


def upload_excel_to_drive(folder_id: str, file_path: Path) -> str:
    """Upload the submitted Excel file into the Drive folder. Returns file ID."""
    drive_service, _ = get_google_services()
    
    file_metadata = {"name": file_path.name, "parents": [folder_id]}
    media = MediaFileUpload(str(file_path), mimetype="application/vnd.ms-excel")

    uploaded = drive_service.files().create(
        body=file_metadata, media_body=media, fields="id"
    ).execute()
    return uploaded["id"]


def convert_excel_to_google_sheet(file_id: str) -> str:
    """Convert uploaded Excel file to Google Sheets. Returns Sheet ID."""
    drive_service, _ = get_google_services()
    
    file = drive_service.files().copy(
        fileId=file_id,
        body={"mimeType": "application/vnd.google-apps.spreadsheet"}
    ).execute()
    return file["id"]


def analyze_with_ai(sheet_id: str) -> Dict[str, Any]:
    """Dummy placeholder for AI analysis. Replace with OpenAI/Gemini logic."""
    # TODO: Replace with real AI call
    return {
        "summary": "AI analyzed the sheet.",
        "recommendations": ["Add more detail", "Double-check formula X"]
    }


def update_protocol_sheet(sheet_id: str, analysis: Dict[str, Any]) -> str:
    """Update a Google Sheet with AI analysis results. Returns updated sheet ID."""
    _, sheets_service = get_google_services()
    
    values = [[analysis["summary"]]] + [[rec] for rec in analysis["recommendations"]]

    sheets_service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range="A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()

    return sheet_id


def export_protocol_to_pdf(sheet_id: str, folder_id: str) -> str:
    """
    Export the sheet to PDF and store in Drive.
    Returns PDF file ID.
    """
    drive_service, _ = get_google_services()
    
    # Google Drive "export" via files().export()
    pdf_content = drive_service.files().export(
        fileId=sheet_id,
        mimeType="application/pdf"
    ).execute()

    # Save to Drive as a new file
    file_metadata = {"name": "Protocol.pdf", "parents": [folder_id]}
    
    # Save PDF content to temporary file
    temp_pdf_path = "protocol.pdf"
    with open(temp_pdf_path, "wb") as f:
        f.write(pdf_content)
    
    media = MediaFileUpload(temp_pdf_path, mimetype="application/pdf")

    uploaded = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()

    # Clean up temporary file
    os.remove(temp_pdf_path)

    return uploaded["id"]
