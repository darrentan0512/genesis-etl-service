from datetime import datetime, timezone
import uuid
from flask import Blueprint, send_file, current_app, request, jsonify
from werkzeug.utils import secure_filename
import pandas as pd
import os
import logging
from app.factory.dynamic_excel_factory import ExcelModelFactory
from app.models.error_response import ErrorResponse
from app import mongo
from app.utils.validation_utils import COLUMN_VALIDATION_CONFIG

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
    logger.info(f"Error here")
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

            # Convert
            required_columns = [col['label'] for col in COLUMN_VALIDATION_CONFIG if col['required']]

            dynamic_excel_columns = dynamic_excel_model_list[0].get_columns()
            validate_store_columns(required_columns, dynamic_excel_columns)
            # Insert the objects into MongoDB
            try:
                collection = mongo.db.employee  # Replace with your collection name
                
                # Process each document individually for upsert operation
                upserted_count = 0
                updated_count = 0
                
                for model in dynamic_excel_model_list:
                    document = model.to_dict()
                    # Assuming email is the unique identifier
                    email = document.get('EMAIL_ADDRESS')
                    phone_number = document.get('PHONE_NUMBER')
                    
                    if not email:
                        logger.warning("Document missing email field, skipping...")
                        continue
                        
                    # Use upsert to update if exists, create if doesn't
                    result = collection.replace_one(
                        {
                            "EMAIL_ADDRESS": email,
                            "PHONE_NUMBER": phone_number  # Both conditions must match
                        },
                        document,  # Update operation
                        upsert=True  # Create if doesn't exist
                    )
                    
                    if result.upserted_id:
                        upserted_count += 1
                    elif result.modified_count > 0:
                        updated_count += 1
                
                logger.info(f"Operation completed: {upserted_count} new documents created, {updated_count} existing documents updated.")
                
            except Exception as e:
                logger.error(f"Error upserting documents into MongoDB: {str(e)}")
                raise ErrorResponse(
                    title="Database Error",
                    status=500,
                    detail="Failed to upsert documents into the database.",
                    errors=str(e)
                )

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
    
def validate_store_columns(default_required_columns, excel_columns):
    snake_case_columns = [col.upper().replace(' ', '_') for col in excel_columns]
    missing_columns = [col for col in default_required_columns if col not in snake_case_columns]
    if missing_columns:
        raise ErrorResponse(
            title="Validation Error",
            status=400,
            detail=f"Missing required columns: {', '.join(missing_columns)}",
            errors=f"Required columns not found in Excel file"
        )
    required_columns = {}
    non_required_columns = {}
    for i, snake_col in enumerate(snake_case_columns):
        original_label = excel_columns[i]
        if snake_col in default_required_columns:
            required_columns[snake_col] = {
                'label': original_label,
                'engine_name': snake_col,
                'description': ''
            }
        else:
            non_required_columns[snake_col] = {
            'label': original_label,
            'engine_name': snake_col,
            'description': ''
        }

    # Create column mapping document
    column_mapping = {
        'required_columns': required_columns,
        'non_required_columns': non_required_columns,
        'created_at': datetime.now(timezone.utc),
        'uuid': str(uuid.uuid4()),
        'version': '1'
    }

    # Insert column mapping into MongoDB
    try:
        collection = mongo.db.employee_column_mapping
        result = collection.insert_one(column_mapping)
        logger.info(f"Inserted profile mapping column mapping with _id: {result.inserted_id}")
    except Exception as e:
        logger.error(f"Error inserting column mapping into MongoDB: {str(e)}")
        raise ErrorResponse(
            title="Database Error",
            status=500,
            detail="Failed to insert column mapping into the database.",
            errors=str(e)
        )