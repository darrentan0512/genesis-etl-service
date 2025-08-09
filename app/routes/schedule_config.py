import random
from flask import Blueprint, request, jsonify
from app.models.error_response import ErrorResponse
from app import mongo
from app.utils.calculating_shift import calculate_total_time_blocks, generate_time_unit_map, get_datetime_from_time_unit, get_time_unit_from_datetime_and_time, inverse_map, shift_types
from bson import ObjectId
from bson.errors import InvalidId
import re
from datetime import datetime, timedelta, timezone

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

def generate_13_digit_uid():
    """Generate a unique 13-digit identifier"""
    # Use timestamp + random for uniqueness
    timestamp = int(datetime.now().timestamp() * 1000)  # milliseconds
    random_part = random.randint(1000, 9999)
    uid_str = f"{timestamp}{random_part}"
    
    # Ensure it's exactly 13 digits
    if len(uid_str) > 13:
        uid_str = uid_str[:13]
    elif len(uid_str) < 13:
        uid_str = uid_str.ljust(13, '0')
    
    return int(uid_str)


def convert_request_to_mongo_format(data):
    """
    Convert request JSON format to MongoDB JSON format
    """
    schedule_period = data['SCHEDULE_PERIOD']
    start_date_str = schedule_period['start_date']
    end_date_str = schedule_period['end_date']
    
    # Parse dates
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    
    # Calculate total time blocks
    time_block_hours = 0.5
    total_time_blocks = calculate_total_time_blocks(start_date_str, end_date_str, time_block_hours)
    
    # Generate time unit mappings
    time_unit_map = generate_time_unit_map(start_date, end_date, time_block_hours)
    datetime_to_unit_map = inverse_map(time_unit_map)
    
    # Group shifts by type and roles
    shift_groups = {}
    
    for shift in data['SHIFT']:
        shift_type = shift['type']
        start_time = shift['start_time']
        end_time = shift['end_time']
        roles = tuple(sorted(shift['role_applied_to']))  # Use tuple for hashable key
        datetime_str = shift['datetime']
        # Create a key for grouping
        group_key = (shift_type, start_time, end_time, roles)
        
        if group_key not in shift_groups:
            shift_groups[group_key] = {
                'type': shift_type,
                'start_time': start_time,
                'end_time': end_time,
                'roles': list(roles),
                'dates': []
            }
        
        shift_groups[group_key]['dates'].append(datetime_str)
    
    # Convert groups to MongoDB format
    mongo_shifts = []
    planning_start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    
    for group_key, group_data in shift_groups.items():
        shift_uid = generate_13_digit_uid()
        shift_type = group_data['type']
        
        # Calculate days_applied_to (day indices from start date)
        days_applied_to = []
        for date_str in group_data['dates']:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            day_index = (date_obj - planning_start_date).days
            days_applied_to.append(day_index)
        
        # Calculate time blocks for start and end times
        # Use the first date to get the time blocks
        first_date = group_data['dates'][0]
        start_time_block = get_time_unit_from_datetime_and_time(
            first_date, group_data['start_time'], datetime_to_unit_map
        )
        end_time_block = get_time_unit_from_datetime_and_time(
            first_date, group_data['end_time'], datetime_to_unit_map
        )
        
        # Handle cross-day shifts (e.g., 17:00 to 01:00 next day)
        if end_time_block is None or (end_time_block <= start_time_block):
            # Try next day for end time
            next_date = (datetime.strptime(first_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
            end_time_block = get_time_unit_from_datetime_and_time(
                next_date, group_data['end_time'], datetime_to_unit_map
            )
        
        mongo_shift = {
            "shift_uid": shift_uid,
            "shift_id": f"{shift_type}_{shift_uid}",
            "start_time_block": start_time_block,
            "type": shift_type,
            "end_time_block": end_time_block,
            "role_applied_to": group_data['roles'],
            "days_applied_to": sorted(days_applied_to)
        }
        
        mongo_shifts.append(mongo_shift)
    
    # Build the final MongoDB document
    mongo_doc = {
        "SCHEDULE_PERIOD": {
            "start_date": start_date_str,
            "end_date": end_date_str,
            "number_of_days": schedule_period['number_of_days'],
            "total_time_block": total_time_blocks
        },
        "DEPARTMENT": data['DEPARTMENT'],
        "SHIFT": mongo_shifts
    }
    
    return mongo_doc

def convert_mongo_to_request_format(mongo_doc):
    """
    Convert MongoDB JSON format back to request JSON format
    """
    
    # Create mapping for quick lookup
    shift_type_mapping = {shift['type']: shift for shift in shift_types}
    
    schedule_period = mongo_doc['SCHEDULE_PERIOD']
    start_date_str = schedule_period['start_date']
    end_date_str = schedule_period['end_date']
    
    # Parse dates
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    
    # Generate time unit mappings
    time_block_hours = 0.5
    time_unit_map = generate_time_unit_map(start_date, end_date, time_block_hours)
    
    # Calculate planning start date for day index conversion
    planning_start_date = start_date.date()
    
    # Convert grouped shifts back to individual shifts
    request_shifts = []
    
    for mongo_shift in mongo_doc['SHIFT']:
        # Use stored type field directly
        shift_type = mongo_shift.get('type')
        if not shift_type:
            # Fallback: extract from shift_id for backward compatibility
            shift_type = mongo_shift['shift_id'].split('_')[0]
        
        # Get start_time and end_time from shift_types mapping
        shift_definition = shift_type_mapping.get(shift_type)
        if shift_definition:
            start_time_str = shift_definition['start_time']
            end_time_str = shift_definition['end_time']
        else:
            # Fallback: calculate from time blocks if shift type not found
            start_time_block = mongo_shift['start_time_block']
            end_time_block = mongo_shift['end_time_block']
            
            start_datetime = get_datetime_from_time_unit(start_time_block, time_unit_map)
            end_datetime = get_datetime_from_time_unit(end_time_block, time_unit_map)
            
            if start_datetime and end_datetime:
                start_time_str = start_datetime.strftime('%H:%M')
                end_time_str = end_datetime.strftime('%H:%M')
            else:
                # Final fallback
                start_time_str, end_time_str = ('00:00', '00:00')
        
        role_applied_to = mongo_shift['role_applied_to']
        days_applied_to = mongo_shift['days_applied_to']
        
        # Create individual shift entries for each day
        for day_index in days_applied_to:
            shift_date = planning_start_date + timedelta(days=day_index)
            shift_date_str = shift_date.strftime('%Y-%m-%d')
            
            request_shift = {
                "datetime": shift_date_str,
                "type": shift_type,
                "start_time": start_time_str,
                "end_time": end_time_str,
                "role_applied_to": role_applied_to.copy()  # Create a copy to avoid reference issues
            }
            
            request_shifts.append(request_shift)
    
    # Sort shifts by datetime and then by start_time for consistent ordering
    request_shifts.sort(key=lambda x: (x['datetime'], x['start_time']))
    
    # Build the request format document
    request_doc = {
        "SCHEDULE_PERIOD": {
            "start_date": start_date_str,
            "end_date": end_date_str,
            "number_of_days": schedule_period['number_of_days']
        },
        "DEPARTMENT": mongo_doc['DEPARTMENT'],
        "SHIFT": request_shifts
    }
    
    return request_doc

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
            
            # Validate datetime
            if 'datetime' not in shift or not shift['datetime']:
                errors.append(f"SHIFT[{i}].datetime is required")
            elif not validate_date_format(shift['datetime']):
                errors.append(f"SHIFT[{i}].datetime must be in YYYY-MM-DD format")
            
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
            
            # Validate role_applied_to
            if 'role_applied_to' not in shift or not shift['role_applied_to']:
                errors.append(f"SHIFT[{i}].role_applied_to is required")
            elif not isinstance(shift['role_applied_to'], list):
                errors.append(f"SHIFT[{i}].role_applied_to must be an array")
            elif len(shift['role_applied_to']) == 0:
                errors.append(f"SHIFT[{i}].role_applied_to array cannot be empty")
    
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
        
        # Convert request format to MongoDB format
        try:
            mongo_doc = convert_request_to_mongo_format(data)
        except Exception as e:
            return jsonify({
                'success': False,
                'message': 'Error converting request data',
                'error': str(e)
            }), 400
        
        # Add timestamps
        mongo_doc['updated_at'] = datetime.now(timezone.utc)
        mongo_doc['created_at'] = datetime.now(timezone.utc)
        
        # Define the filter for upsert (using DEPARTMENT as the unique identifier)
        filter_criteria = {'DEPARTMENT': data['DEPARTMENT']}
        
        # Perform upsert operation
        result = mongo.db.schedule_config.update_one(
            filter_criteria,
            {
                '$set': {
                    'SCHEDULE_PERIOD': mongo_doc['SCHEDULE_PERIOD'],
                    'DEPARTMENT': mongo_doc['DEPARTMENT'],
                    'SHIFT': mongo_doc['SHIFT'],
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
                'data': serialized_doc,
                'conversion_summary': {
                    'total_time_blocks': mongo_doc['SCHEDULE_PERIOD']['total_time_block'],
                    'unique_shifts_created': len(mongo_doc['SHIFT']),
                    'input_shifts_count': len(data['SHIFT'])
                }
            }), 201
        else:
            # Document was updated
            updated_doc = mongo.db.schedule_config.find_one(filter_criteria)
            serialized_doc = serialize_mongo_doc(updated_doc)
            
            return jsonify({
                'success': True,
                'message': 'Schedule configuration updated successfully',
                'data': serialized_doc,
                'conversion_summary': {
                    'total_time_blocks': mongo_doc['SCHEDULE_PERIOD']['total_time_block'],
                    'unique_shifts_created': len(mongo_doc['SHIFT']),
                    'input_shifts_count': len(data['SHIFT'])
                }
            }), 200
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error processing schedule configuration',
            'error': str(e)
        }), 500
    

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
        
        # Convert MongoDB format to request format
        try:
            request_format_data = convert_mongo_to_request_format(schedule_config)
        except Exception as e:
            return jsonify({
                'success': False,
                'message': 'Error converting schedule configuration',
                'error': str(e)
            }), 500
        
        return jsonify({
            'success': True,
            'message': 'Schedule configuration retrieved successfully',
            'data': request_format_data,
            'conversion_summary': {
                'total_shifts_expanded': len(request_format_data['SHIFT']),
                'unique_shift_groups_in_db': len(schedule_config['SHIFT']),
                'planning_period_days': request_format_data['SCHEDULE_PERIOD']['number_of_days']
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error fetching schedule configuration',
            'error': str(e)
        }), 500