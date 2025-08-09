import random
from flask import Blueprint, request, jsonify
from app.models.error_response import ErrorResponse
from app import mongo
from app.utils.calculating_shift import  shift_types
import re

overall_config_bp = Blueprint('overall_config', __name__, url_prefix='/api/configs')

# GET /api/employees/<id> - Get employee by ID
@overall_config_bp.route('/shift_type', methods=['GET'])
def get_shift_type():
    try:
        return jsonify({
            'success': True,
            'data': shift_types
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error fetching shift_type',
            'error': str(e)
        }), 500


@overall_config_bp.route('/department_list', methods=['GET'])
def get_department_list():
    try:
        # Find all employees and extract unique departments
        employees = mongo.db.employee.find({}, {"DEPARTMENT": 1})
        
        # Extract unique departments, filter out None/null values
        departments = set()
        for employee in employees:
            if employee.get("DEPARTMENT"):
                departments.add(employee["DEPARTMENT"])
        
        # Convert to list and add DEFAULT option
        department_list = sorted(list(departments))
        department_list.insert(0, "DEFAULT")
        
        return jsonify({
            'success': True,
            'data': department_list
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error fetching department list from employee db',
            'error': str(e)
        }), 500

@overall_config_bp.route('/role_list', methods=['GET'])
def get_role_list():
    try:
        # Find all employees and extract unique roles
        employees = mongo.db.employee.find({}, {"ROLE": 1})
        
        # Extract unique roles, filter out None/null values
        roles = set()
        for employee in employees:
            if employee.get("ROLE"):
                roles.add(employee["ROLE"])
        
        # Convert to list and add DEFAULT option
        role_list = sorted(list(roles))
        role_list.insert(0, "DEFAULT")
        
        return jsonify({
            'success': True,
            'data': role_list
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error fetching role list from employee db',
            'error': str(e)
        }), 500