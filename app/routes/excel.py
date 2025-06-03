from flask import Blueprint, send_file, current_app, request, jsonify
from werkzeug.utils import secure_filename
import pandas as pd
import os
import logging
from app.factory.dynamic_excel_factory import ExcelModelFactory
from app.models.error_response import ErrorResponse

SAMPLE_EXCEL_FILE = 'Sample Excel.xlsx'

excel_bp = Blueprint('excel', __name__, url_prefix='/api/excel')
logger = logging.getLogger(__name__)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

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
    
@excel_bp.route('/upload', methods=['POST'])
def upload_excel():
    # Check if the post request has the file part


    if len(request.files) == 0:
        return jsonify({
            'success': False,
            'error': 'No file part in the request'
        }), 400
    
    # Only the first file is processed
    
    file_keys = list(request.files.keys())
    file_name = file_keys[0]

    file = request.files[file_name]
    # If user doesn't select file, the browser submits an empty file without filename0
    
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            
            # Make sure the resource directory exists
            resource_dir = os.path.join(current_app.root_path, current_app.config['RESOURCE_FOLDER'])
            os.makedirs(resource_dir, exist_ok=True)
            
            # Construct full file path
            filepath = os.path.join(resource_dir, filename)
            logger.info(f"Saving file to: {filepath}")
            
            # Save the file
            file.save(filepath)
            
            # Process the Excel file
            dynamic_excel_model_list = ExcelModelFactory.from_excel_file(filepath)
            
            # Example processing: Get basic info about the file
            file_info = {
                'filename': filename,
                'rows': len(dynamic_excel_model_list),
                'columns': len(dynamic_excel_model_list[0].get_columns()),
                'column_names': dynamic_excel_model_list[0].get_columns(),
                # 'preview': df.head(5).to_dict(orient='records')
            }

            logger.info(f"Successfully processed file: {filename}")
            
            # Return JSON response
            return jsonify({
                'success': True,
                'message': 'File uploaded successfully',
                'file_info': file_info
            }), 200
                
        except ErrorResponse as e:
            return e.to_response()
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            return jsonify({
            'success': False,
            'error': f'File processing error {str(e)}'
        }), 400
    else:
        allowed = ', '.join(current_app.config['ALLOWED_EXTENSIONS'])
        return jsonify({
            'success': False,
            'error': f'Invalid file type. Allowed file types are: {allowed}'
        }), 400