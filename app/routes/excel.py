from flask import Blueprint, send_file, current_app
import os

SAMPLE_EXCEL_FILE = 'Sample Excel.xlsx'

excel_bp = Blueprint('excel', __name__, url_prefix='/api/excel')

@excel_bp.route('/download')
def download_excel():
    """
    Download an Excel file from the resources directory
    
    Args:
        filename (str): Name of the Excel file to download
    
    Returns:
        Flask response with the Excel file as an attachment
    """
    try:
        # Validate filename to prevent directory traversal attacks
        
        # Construct full file path
        file_path = os.path.join(current_app.root_path, current_app.config["RESOURCE_FOLDER"], SAMPLE_EXCEL_FILE)
        
        # Check if file exists
        if not os.path.exists(file_path):
            return "File not found", 404
        
        # Send the file as an attachment
        return send_file(
            file_path,
            as_attachment=True,
            download_name=SAMPLE_EXCEL_FILE,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        # Log the error (in a real application, use proper logging)
        print(f"Error downloading file {SAMPLE_EXCEL_FILE}: {e}")
        return "Internal server error", 500