from flask import Blueprint, render_template, redirect, url_for, request, Response, flash, send_file
from .. import db
from ..models import Project, Loan, Tranche, Adjustment
from datetime import datetime
import csv
from io import StringIO, BytesIO
import pandas as pd
import zipfile

export_bp = Blueprint('export', __name__)

@export_bp.route('/export/<export_type>/<file_type>')
def export_data(export_type, file_type):
    if export_type == 'projects':
        # Fetch all data from the 'Project' table and convert it to DataFrame
        query = db.session.query(Project).all()
        df = pd.DataFrame([project.__dict__ for project in query])  # Convert each project to a dict
        df = df.drop(columns=['_sa_instance_state'])  # Drop the SQLAlchemy instance state column
        return export_single(df, file_type, 'projects')
    
    elif export_type == 'loans':
        # Fetch all data from the 'Project' table and convert it to DataFrame
        query = db.session.query(Loan).all()
        df = pd.DataFrame([loan.__dict__ for loan in query])  # Convert each project to a dict
        df = df.drop(columns=['_sa_instance_state'])  # Drop the SQLAlchemy instance state column
        return export_single(df, file_type, 'loans')

    elif export_type == 'tranches':
        # Fetch all data from the 'Project' table and convert it to DataFrame
        query = db.session.query(Tranche).all()
        df = pd.DataFrame([tranche.__dict__ for tranche in query])  # Convert each project to a dict
        df = df.drop(columns=['_sa_instance_state'])  # Drop the SQLAlchemy instance state column
        return export_single(df, file_type, 'tranches')

    elif export_type == 'adjustments':
        # Fetch all data from the 'Project' table and convert it to DataFrame
        query = db.session.query(Adjustment).all()
        df = pd.DataFrame([adjustment.__dict__ for adjustment in query])  # Convert each project to a dict
        df = df.drop(columns=['_sa_instance_state'])  # Drop the SQLAlchemy instance state column
        return export_single(df, file_type, 'adjustments')
    
    elif export_type == 'all':
        return export_all_tables(file_type)

    return Response("Invalid export type", status=400)


def export_single(df, file_type, base_name):
    output = BytesIO()
    
    # Check for file type and export the DataFrame
    if file_type == 'excel':
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name=base_name.title())
        output.seek(0)
        return send_file(output, download_name=f"{base_name}.xlsx", as_attachment=True)
    
    elif file_type == 'csv':
        csv_data = df.to_csv(index=False)
        return Response(csv_data, mimetype='text/csv', headers={
            "Content-Disposition": f"attachment; filename={base_name}.csv"
        })
    
    return Response("Unsupported file format", status=400)


def export_all_tables(file_type):
    metadata = db.MetaData()
    metadata.reflect(bind=db.engine)  # Get all tables from the database schema
    output = BytesIO()

    if file_type == 'excel':
        # Create a single Excel file with all tables as different sheets
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for table_name in metadata.tables:
                table = metadata.tables[table_name]  # Get the SQLAlchemy table object
                df = pd.read_sql_table(table_name, db.engine)  # Use pd.read_sql_table for each table
                # Write each table to a different sheet in the Excel file
                df.to_excel(writer, index=False, sheet_name=table_name[:31])  # Sheet name limit to 31 chars
        output.seek(0)
        return send_file(output, download_name="all_data.xlsx", as_attachment=True)

    elif file_type == 'csv':
        # Create a zip file with each table's CSV data
        with zipfile.ZipFile(output, 'w') as zipf:
            for table_name in metadata.tables:
                df = pd.read_sql_table(table_name, db.engine)  # Use pd.read_sql_table for each table
                csv_bytes = df.to_csv(index=False).encode('utf-8')
                zipf.writestr(f"{table_name}.csv", csv_bytes)
        output.seek(0)
        return send_file(output, download_name="all_data_csv.zip", as_attachment=True, mimetype='application/zip')

    return Response("Unsupported file format", status=400)