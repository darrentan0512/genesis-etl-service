from flask import Blueprint, request, jsonify
from app.models.error_response import ErrorResponse
from app import mongo
from flask import Blueprint, request, jsonify
from bson import ObjectId
from bson.errors import InvalidId
import re
from datetime import datetime, timezone

employee_column_mapping_bp = Blueprint('employee_column', __name__, url_prefix='/api/employee_column')

def serialize_mongo_doc(doc):
    return {k: str(v) if isinstance(v, ObjectId) else v for k, v in doc.items()}

def serialize_staff_mapping(doc):
    doc['_id'] = str(doc['_id'])

    # Convert dict → list of values
    if 'required_columns' in doc and isinstance(doc['required_columns'], dict):
        doc['required_columns'] = list(doc['required_columns'].values())

    if 'non_required_columns' in doc and isinstance(doc['non_required_columns'], dict):
        doc['non_required_columns'] = list(doc['non_required_columns'].values())

    return doc

# GET /api/profile_mapping - Get all profile_mapping
@employee_column_mapping_bp.route('', methods=['GET'])
def get_profile_mapping():
    try:
        # Execute query to get all profile mappings
        mappings = list(mongo.db.employee_column_mapping.find())
        serialized_staff_mapping = [serialize_staff_mapping(staff) for staff in mappings]
        
        return jsonify({
            'success': True,
            'data': serialized_staff_mapping
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error fetching profile mappings',
            'error': str(e)
        }), 500
    
# POST /api/profile_mapping - Update profile mapping by UUID
@employee_column_mapping_bp.route('', methods=['POST'])
def update_profile_mapping():
    try:
        data = request.get_json()
        mapping_uuid = data.get('uuid')
        
        if not mapping_uuid:
            return jsonify({
                'success': False,
                'message': 'UUID is required'
            }), 400
        
        # Find existing mapping
        existing_mapping = mongo.db.employee_column_mapping.find_one({'uuid': mapping_uuid})
        if not existing_mapping:
            return jsonify({
                'success': False,
                'message': 'Profile mapping not found'
            }), 404
        
        # Get current columns
        required_columns = existing_mapping.get('required_columns', {})
        non_required_columns = existing_mapping.get('non_required_columns', {})
        
        # Process updates from request data (array format)
        new_required = data.get('required_columns', [])
        new_non_required = data.get('non_required_columns', [])
        
        # Update required columns from array
        for column_data in new_required:
            engine_name = column_data.get('engine_name')
            if not engine_name:
                continue
                
            if engine_name in required_columns:
                # Update existing (preserve engine_name)
                required_columns[engine_name]['label'] = column_data.get('label', required_columns[engine_name]['label'])
                required_columns[engine_name]['description'] = column_data.get('description', required_columns[engine_name]['description'])
            else:
                # Add new column
                required_columns[engine_name] = {
                    'label': column_data.get('label', ''),
                    'engine_name': engine_name,
                    'description': column_data.get('description', '')
                }
        
        # Update non-required columns from array
        for column_data in new_non_required:
            engine_name = column_data.get('engine_name')
            if not engine_name:
                continue
                
            if engine_name in non_required_columns:
                # Update existing (preserve engine_name)
                non_required_columns[engine_name]['label'] = column_data.get('label', non_required_columns[engine_name]['label'])
                non_required_columns[engine_name]['description'] = column_data.get('description', non_required_columns[engine_name]['description'])
            else:
                # Add new column
                non_required_columns[engine_name] = {
                    'label': column_data.get('label', ''),
                    'engine_name': engine_name,
                    'description': column_data.get('description', '')
                }
        
        # Increment version
        new_version = str(int(existing_mapping.get('version', '1')) + 1)
        
        # Update document
        updated_mapping = {
            'required_columns': required_columns,
            'non_required_columns': non_required_columns,
            'created_at': existing_mapping.get('created_at'),
            'updated_at': datetime.now(timezone.utc),
            'uuid': mapping_uuid,
            'version': new_version
        }
        
        result = mongo.db.employee_column_mapping.update_one(
            {'uuid': mapping_uuid},
            {'$set': updated_mapping}
        )
        
        if result.modified_count > 0:
            return jsonify({
                'success': True,
                'message': 'Profile mapping updated successfully',
                'data': {
                    'uuid': mapping_uuid,
                    'version': new_version,
                    'required_columns': required_columns,
                    'non_required_columns': non_required_columns
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'No changes made to profile mapping'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error updating profile mapping',
            'error': str(e)
        }), 500