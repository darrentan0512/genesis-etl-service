from flask import Blueprint, request, jsonify
from app.models.error_response import ErrorResponse
from app import mongo
from bson import ObjectId
from bson.errors import InvalidId
import re
from datetime import datetime, timezone

schedule_config_bp = Blueprint('schedule_config', __name__, url_prefix='/api/schedule_config')

def serialize_mongo_doc(doc):
    return {k: str(v) if isinstance(v, ObjectId) else v for k, v in doc.items()}

def validate_date_format(date_string):
    """Validate date format YYYY-MM-DD"""
    try:
        datetime.strptime(date_string, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def validate_time_format(time_string):
    """Validate time format HH:MM"""
    try:
        datetime.strptime(time_string, '%H:%M')
        return True
    except ValueError:
        return False

def validate_schedule_config(data):
    """Validate the incoming schedule config data"""
    errors = []
    
    # Check required fields
    if 'SCHEDULE_PERIOD' not in data:
        errors.append("SCHEDULE_PERIOD is required")
    else:
        schedule_period = data['SCHEDULE_PERIOD']
        
        # Validate start_date
        if 'start_date' not in schedule_period or not schedule_period['start_date']:
            errors.append("SCHEDULE_PERIOD.start_date is required")
        elif not validate_date_format(schedule_period['start_date']):
            errors.append("SCHEDULE_PERIOD.start_date must be in YYYY-MM-DD format")
        
        # Validate end_date
        if 'end_date' not in schedule_period or not schedule_period['end_date']:
            errors.append("SCHEDULE_PERIOD.end_date is required")
        elif not validate_date_format(schedule_period['end_date']):
            errors.append("SCHEDULE_PERIOD.end_date must be in YYYY-MM-DD format")
        
        # Validate number_of_days
        if 'number_of_days' not in schedule_period:
            errors.append("SCHEDULE_PERIOD.number_of_days is required")
        elif not isinstance(schedule_period['number_of_days'], int) or schedule_period['number_of_days'] <= 0:
            errors.append("SCHEDULE_PERIOD.number_of_days must be a positive integer")
        
        # Validate date range logic
        if 'start_date' in schedule_period and 'end_date' in schedule_period:
            if validate_date_format(schedule_period['start_date']) and validate_date_format(schedule_period['end_date']):
                start_date = datetime.strptime(schedule_period['start_date'], '%Y-%m-%d')
                end_date = datetime.strptime(schedule_period['end_date'], '%Y-%m-%d')
                if start_date > end_date:
                    errors.append("SCHEDULE_PERIOD.start_date cannot be after end_date")
    
    # Validate DEPARTMENT
    if 'DEPARTMENT' not in data or not data['DEPARTMENT']:
        errors.append("DEPARTMENT is required")
    elif not isinstance(data['DEPARTMENT'], str):
        errors.append("DEPARTMENT must be a string")
    
    # Validate SHIFT
    if 'SHIFT' not in data:
        errors.append("SHIFT is required")
    elif not isinstance(data['SHIFT'], list):
        errors.append("SHIFT must be an array")
    elif len(data['SHIFT']) == 0:
        errors.append("SHIFT array cannot be empty")
    else:
        for i, shift in enumerate(data['SHIFT']):
            if not isinstance(shift, dict):
                errors.append(f"SHIFT[{i}] must be an object")
                continue
            
            # Validate TYPE
            if 'type' not in shift or not shift['type']:
                errors.append(f"SHIFT[{i}].type is required")
            elif not isinstance(shift['type'], str):
                errors.append(f"SHIFT[{i}].type must be a string")
            
            # Validate start_time
            if 'start_time' not in shift or not shift['start_time']:
                errors.append(f"SHIFT[{i}].start_time is required")
            elif not validate_time_format(shift['start_time']):
                errors.append(f"SHIFT[{i}].start_time must be in HH:MM format")
            
            # Validate end_time
            if 'end_time' not in shift or not shift['end_time']:
                errors.append(f"SHIFT[{i}].end_time is required")
            elif not validate_time_format(shift['end_time']):
                errors.append(f"SHIFT[{i}].end_time must be in HH:MM format")
    
    return errors

# POST /api/schedule_config - Create or update schedule configuration
@schedule_config_bp.route('', methods=['POST'])
def upsert_schedule_config():
    try:
        # Get JSON data from request
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Request body is required'
            }), 400
        
        # Validate the incoming data
        validation_errors = validate_schedule_config(data)
        if validation_errors:
            return jsonify({
                'success': False,
                'message': 'Validation failed',
                'errors': validation_errors
            }), 400
        
        # Prepare the document for upsert
        schedule_config_doc = {
            'SCHEDULE_PERIOD': data['SCHEDULE_PERIOD'],
            'DEPARTMENT': data['DEPARTMENT'],
            'SHIFT': data['SHIFT'],
            'updated_at': datetime.now(timezone.utc),
            'created_at': datetime.now(timezone.utc)
        }
        
        # Define the filter for upsert (you might want to adjust this based on your business logic)
        # Currently using DEPARTMENT as the unique identifier
        filter_criteria = {'DEPARTMENT': data['DEPARTMENT']}
        
        # Perform upsert operation
        result = mongo.db.schedule_config.update_one(
            filter_criteria,
            {
                '$set': {
                    'SCHEDULE_PERIOD': data['SCHEDULE_PERIOD'],
                    'DEPARTMENT': data['DEPARTMENT'],
                    'SHIFT': data['SHIFT'],
                    'updated_at': datetime.now(timezone.utc)
                },
                '$setOnInsert': {
                    'created_at': datetime.now(timezone.utc)
                }
            },
            upsert=True
        )
        
        # Determine if it was an insert or update
        if result.upserted_id:
            # Document was inserted
            inserted_doc = mongo.db.schedule_config.find_one({'_id': result.upserted_id})
            serialized_doc = serialize_mongo_doc(inserted_doc)
            
            return jsonify({
                'success': True,
                'message': 'Schedule configuration created successfully',
                'data': serialized_doc
            }), 201
        else:
            # Document was updated
            updated_doc = mongo.db.schedule_config.find_one(filter_criteria)
            serialized_doc = serialize_mongo_doc(updated_doc)
            
            return jsonify({
                'success': True,
                'message': 'Schedule configuration updated successfully',
                'data': serialized_doc
            }), 200
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error processing schedule configuration',
            'error': str(e)
        }), 500
    

# GET /api/schedule_config - Get schedule configuration by department
@schedule_config_bp.route('', methods=['GET'])
def get_schedule_config():
    try:
        # Get department from headers
        department = request.headers.get('department')
        
        if not department:
            return jsonify({
                'success': False,
                'message': 'Department header is required'
            }), 400
        
        # Query the database
        schedule_config = mongo.db.schedule_config.find_one({'DEPARTMENT': department})
        
        if not schedule_config:
            return jsonify({
                'success': False,
                'message': f'Schedule configuration not found for department: {department}'
            }), 404
        
        # Serialize the document
        serialized_config = serialize_mongo_doc(schedule_config)
        
        return jsonify({
            'success': True,
            'data': serialized_config
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error fetching schedule configuration',
            'error': str(e)
        }), 500