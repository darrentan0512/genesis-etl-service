import re
from typing import List, Dict, Any, Callable, Optional

# Employee validation configuration
COLUMN_VALIDATION_CONFIG = [
    {
        'label': 'NAME',
        'type': 'string',
        'required': True,
        'min_length': 2,
        'max_length': 100
    },
    {
        'label': 'EMAIL_ADDRESS',
        'type': 'email',
        'required': True
    },
    {
        'label': 'ROLE',
        'type': 'string',
        'required': True
    },
    {
        'label': 'DEPARTMENT',
        'type': 'string',
        'required': True
    },
    {
        'label': 'PHONE_NUMBER',
        'type': 'phone',
        'required': True
    },
    {
        'label': 'IS_PART_TIME',
        'type': 'boolean_string',
        'required': True,
        'valid_values': ['Yes', 'No']
    },
    {
        'label': 'END_OF_PROBATION',
        'type': 'boolean_string',
        'required': True,
        'valid_values': ['Yes', 'No']
    },
    {
        'label': 'SALARY',
        'type': 'float',
        'required': False,
        'min_value': 0
    },
    {
        'label': 'AGE',
        'type': 'integer',
        'required': False,
        'min_value': 16,
        'max_value': 100
    }
]

def is_valid_email(email):
    """Validate email format"""
    pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    return re.match(pattern, email) is not None


def validate_data(data: Dict[str, Any], validation_config: List[Dict]) -> List[str]:
    """
    Generic data validation function
    
    Args:
        data: Dictionary containing the data to validate
        validation_config: List of validation rules
        
    Returns:
        List of error messages
    """
    errors = []
    
    for rule in validation_config:
        field_name = rule['label']
        field_type = rule['type']
        value = data.get(field_name)
        
        # Check if field is required
        if rule.get('required', True):
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(f'{field_name} is required')
                continue
        
        # Skip validation if field is not required and empty
        if not rule.get('required', True) and (value is None or value == ''):
            continue
            
        # Type-specific validation
        if field_type == 'string':
            if not isinstance(value, str) or not value.strip():
                errors.append(f'{field_name} must be a non-empty string')
        
        elif field_type == 'email':
            if not isinstance(value, str) or not is_valid_email(value.strip()):
                errors.append(f'Valid {field_name} is required')
        
        elif field_type == 'phone':
            if not str(value).isdigit():
                errors.append(f'Valid {field_name} is required')
        
        elif field_type == 'boolean_string':
            valid_values = rule.get('valid_values', ['Yes', 'No'])
            if value not in valid_values:
                errors.append(f'{field_name} must be one of: {", ".join(valid_values)}')
        
        elif field_type == 'integer':
            try:
                int(value)
            except (ValueError, TypeError):
                errors.append(f'{field_name} must be a valid integer')
        
        elif field_type == 'float':
            try:
                float(value)
            except (ValueError, TypeError):
                errors.append(f'{field_name} must be a valid number')
        
        elif field_type == 'choice':
            valid_choices = rule.get('choices', [])
            if value not in valid_choices:
                errors.append(f'{field_name} must be one of: {", ".join(map(str, valid_choices))}')
        
        # Custom validation function
        if 'validation' in rule and callable(rule['validation']):
            try:
                is_valid = rule['validation'](value)
                if not is_valid:
                    error_msg = rule.get('error_message', f'{field_name} is invalid')
                    errors.append(error_msg)
            except Exception as e:
                errors.append(f'{field_name} validation failed: {str(e)}')
        
        # Min/Max length validation for strings
        if field_type == 'string' and isinstance(value, str):
            if 'min_length' in rule and len(value.strip()) < rule['min_length']:
                errors.append(f'{field_name} must be at least {rule["min_length"]} characters long')
            if 'max_length' in rule and len(value.strip()) > rule['max_length']:
                errors.append(f'{field_name} must be no more than {rule["max_length"]} characters long')
        
        # Min/Max value validation for numbers
        if field_type in ['integer', 'float']:
            try:
                num_value = float(value) if field_type == 'float' else int(value)
                if 'min_value' in rule and num_value < rule['min_value']:
                    errors.append(f'{field_name} must be at least {rule["min_value"]}')
                if 'max_value' in rule and num_value > rule['max_value']:
                    errors.append(f'{field_name} must be no more than {rule["max_value"]}')
            except (ValueError, TypeError):
                pass  # Type validation already handled above
    
    return errors





def validate_employee_dynamic(employee_data: Dict[str, Any]) -> List[str]:
    """Validate employee data using the configuration"""
    return validate_data(employee_data, COLUMN_VALIDATION_CONFIG)
