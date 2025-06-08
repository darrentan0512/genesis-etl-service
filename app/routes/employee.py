from flask import Blueprint, send_file, current_app, request, jsonify
from app.models.error_response import ErrorResponse
from app import mongo
from flask import Blueprint, request, jsonify
from bson import ObjectId
from bson.errors import InvalidId
import re
from datetime import datetime

employee_bp = Blueprint('employee', __name__, url_prefix='/api/employee')

def validate_employee(employee_data):
    """Validate employee data"""
    errors = []
    
    if not employee_data.get('NAME') or not employee_data['NAME'].strip():
        errors.append('NAME is required')
    
    email = employee_data.get('EMAIL_ADDRESS', '').strip()
    if not email or not is_valid_email(email):
        errors.append('Valid EMAIL_ADDRESS is required')
    
    if not employee_data.get('ROLE') or not employee_data['ROLE'].strip():
        errors.append('ROLE is required')
    
    if not employee_data.get('DEPARTMENT') or not employee_data['DEPARTMENT'].strip():
        errors.append('DEPARTMENT is required')
    
    phone = employee_data.get('PHONE_NUMBER')
    if not phone or not str(phone).isdigit():
        errors.append('Valid PHONE_NUMBER is required')
    
    if employee_data.get('IS_PART_TIME') not in ['Yes', 'No']:
        errors.append('IS_PART_TIME must be "Yes" or "No"')
    
    if employee_data.get('END_OF_PROBATION') not in ['Yes', 'No']:
        errors.append('END_OF_PROBATION must be "Yes" or "No"')
    
    return errors

def is_valid_email(email):
    """Validate email format"""
    pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    return re.match(pattern, email) is not None

def serialize_employee(employee):
    """Convert MongoDB document to JSON serializable format"""
    if employee and '_id' in employee:
        employee['_id'] = str(employee['_id'])
    return employee

# GET /api/employees - Get all employees
@employee_bp.route('', methods=['GET'])
def get_employees():
    try:
        # Query parameters
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        department = request.args.get('department')
        role = request.args.get('role')
        is_part_time = request.args.get('is_part_time')
        
        skip = (page - 1) * limit
        
        # Build filter
        filter_query = {}
        if department:
            filter_query['DEPARTMENT'] = {'$regex': department, '$options': 'i'}
        if role:
            filter_query['ROLE'] = {'$regex': role, '$options': 'i'}
        if is_part_time:
            filter_query['IS_PART_TIME'] = is_part_time
        
        # Execute query
        employees = list(mongo.db.employee.find(filter_query).skip(skip).limit(limit))
        total = mongo.db.employee.count_documents(filter_query)
        
        # Serialize employees
        serialized_employees = [serialize_employee(emp) for emp in employees]
        
        return jsonify({
            'success': True,
            'data': serialized_employees,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'pages': (total + limit - 1) // limit
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error fetching employees',
            'error': str(e)
        }), 500
# GET /api/employees/<id> - Get employee by ID
@employee_bp.route('/<employee_id>', methods=['GET'])
def get_employee(employee_id):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(employee_id):
            return jsonify({
                'success': False,
                'message': 'Invalid employee ID format'
            }), 400
        
        employee = mongo.db.employee.find_one({'_id': ObjectId(employee_id)})
        
        if not employee:
            return jsonify({
                'success': False,
                'message': 'Employee not found'
            }), 404
        
        return jsonify({
            'success': True,
            'data': serialize_employee(employee)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error fetching employee',
            'error': str(e)
        }), 500

# POST /api/employees - Create new employee
@employee_bp.route('', methods=['POST'])
def create_employee():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Define mandatory fields with their processing rules
        mandatory_fields = {
            'ROLE': lambda x: x.strip() if x else '',
            'EMAIL_ADDRESS': lambda x: x.lower().strip() if x else '',
            'NAME': lambda x: x.upper().strip() if x else '',
            'IS_PART_TIME': lambda x: x,
            'PHONE_NUMBER': lambda x: int(x) if str(x).isdigit() else None,
            'DEPARTMENT': lambda x: x.strip() if x else '',
            'END_OF_PROBATION': lambda x: x
        }
        
        # Start with all incoming data (for dynamic fields)
        employee_data = dict(data)
        
        # Process mandatory fields with their specific formatting rules
        for field, processor in mandatory_fields.items():
            if field in data:
                employee_data[field] = processor(data[field])
            else:
                # Set default values for missing mandatory fields
                if field == 'PHONE_NUMBER':
                    employee_data[field] = None
                else:
                    employee_data[field] = ''
        
        # Validate only the mandatory fields
        mandatory_data = {field: employee_data[field] for field in mandatory_fields.keys()}
        validation_errors = validate_employee(mandatory_data)
        
        if validation_errors:
            return jsonify({
                'success': False,
                'message': 'Validation failed',
                'errors': validation_errors
            }), 400
        
        # Check if email already exists
        existing_employee = mongo.db.employee.find_one({
            'EMAIL_ADDRESS': employee_data['EMAIL_ADDRESS']
        })
        
        if existing_employee:
            return jsonify({
                'success': False,
                'message': 'Employee with this email already exists'
            }), 409
        
        # Add timestamps
        employee_data['created_at'] = datetime.utcnow()
        employee_data['updated_at'] = datetime.utcnow()
        
        # Insert employee (with all fields - mandatory + dynamic)
        result = mongo.db.employee.insert_one(employee_data)
        
        # Fetch the created employee
        new_employee = mongo.db.employee.find_one({'_id': result.inserted_id})
        
        return jsonify({
            'success': True,
            'message': 'Employee created successfully',
            'data': serialize_employee(new_employee)
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error creating employee',
            'error': str(e)
        }), 500

# PUT /api/employees/<id> - Update employee
@employee_bp.route('/<employee_id>', methods=['PUT'])
def update_employee(employee_id):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(employee_id):
            return jsonify({
                'success': False,
                'message': 'Invalid employee ID format'
            }), 400
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Check if employee exists
        existing_employee = mongo.db.employee.find_one({'_id': ObjectId(employee_id)})
        if not existing_employee:
            return jsonify({
                'success': False,
                'message': 'Employee not found'
            }), 404
        
        # Define mandatory fields with their processing rules
        mandatory_field_processors = {
            'ROLE': lambda x: x.strip() if x else '',
            'EMAIL_ADDRESS': lambda x: x.lower().strip() if x else '',
            'NAME': lambda x: x.upper().strip() if x else '',
            'IS_PART_TIME': lambda x: x,
            'PHONE_NUMBER': lambda x: int(x) if str(x).isdigit() else None,
            'DEPARTMENT': lambda x: x.strip() if x else '',
            'END_OF_PROBATION': lambda x: x
        }
        
        # Start with all incoming data (for dynamic fields)
        update_data = dict(data)
        
        # Process mandatory fields if they're being updated
        for field, processor in mandatory_field_processors.items():
            if field in data:
                update_data[field] = processor(data[field])
        
        # Merge with existing data for validation (only mandatory fields)
        merged_mandatory_data = {}
        for field in mandatory_field_processors.keys():
            if field in update_data:
                merged_mandatory_data[field] = update_data[field]
            else:
                merged_mandatory_data[field] = existing_employee.get(field)
        
        # Validate merged mandatory data
        validation_errors = validate_employee(merged_mandatory_data)
        if validation_errors:
            return jsonify({
                'success': False,
                'message': 'Validation failed',
                'errors': validation_errors
            }), 400
        
        # Check email uniqueness if email is being updated
        if 'EMAIL_ADDRESS' in update_data:
            email_exists = mongo.db.employee.find_one({
                'EMAIL_ADDRESS': update_data['EMAIL_ADDRESS'],
                '_id': {'$ne': ObjectId(employee_id)}
            })
            
            if email_exists:
                return jsonify({
                    'success': False,
                    'message': 'Employee with this email already exists'
                }), 409
        
        # Add update timestamp
        update_data['updated_at'] = datetime.utcnow()
        
        # Update employee (with all fields - mandatory + dynamic)
        result = mongo.db.employee.update_one(
            {'_id': ObjectId(employee_id)},
            {'$set': update_data}
        )
        
        if result.modified_count == 0:
            return jsonify({
                'success': False,
                'message': 'No changes made to employee'
            }), 200
        
        # Fetch updated employee
        updated_employee = mongo.db.employee.find_one({'_id': ObjectId(employee_id)})
        
        return jsonify({
            'success': True,
            'message': 'Employee updated successfully',
            'data': serialize_employee(updated_employee)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error updating employee',
            'error': str(e)
        }), 500

# DELETE /api/employees/<id> - Delete employee
@employee_bp.route('/<employee_id>', methods=['DELETE'])
def delete_employee(employee_id):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(employee_id):
            return jsonify({
                'success': False,
                'message': 'Invalid employee ID format'
            }), 400
        
        # Check if employee exists
        employee = mongo.find_one({'_id': ObjectId(employee_id)})
        if not employee:
            return jsonify({
                'success': False,
                'message': 'Employee not found'
            }), 404
        
        # Delete employee
        result = mongo.delete_one({'_id': ObjectId(employee_id)})
        
        if result.deleted_count == 0:
            return jsonify({
                'success': False,
                'message': 'Failed to delete employee'
            }), 500
        
        return jsonify({
            'success': True,
            'message': 'Employee deleted successfully',
            'data': serialize_employee(employee)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error deleting employee',
            'error': str(e)
        }), 500

# GET /api/employees/search - Search employees
@employee_bp.route('/search', methods=['GET'])
def search_employees():
    try:
        query = request.args.get('q', '').strip()
        
        if not query:
            return jsonify({
                'success': False,
                'message': 'Search query is required'
            }), 400
        
        # Search in multiple fields
        search_filter = {
            '$or': [
                {'NAME': {'$regex': query, '$options': 'i'}},
                {'EMAIL_ADDRESS': {'$regex': query, '$options': 'i'}},
                {'ROLE': {'$regex': query, '$options': 'i'}},
                {'DEPARTMENT': {'$regex': query, '$options': 'i'}}
            ]
        }
        
        employees = list(mongo.find(search_filter).limit(20))
        serialized_employees = [serialize_employee(emp) for emp in employees]
        
        return jsonify({
            'success': True,
            'data': serialized_employees,
            'count': len(serialized_employees)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error searching employees',
            'error': str(e)
        }), 500