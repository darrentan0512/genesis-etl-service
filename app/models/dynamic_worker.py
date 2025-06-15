import pandas as pd
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
import json

class DynamicExcelModel:
    """
    A flexible model class that adapts to Excel files with varying column structures.
    Supports dynamic attribute creation, data validation, and type conversion.
    """
    
    def __init__(self, **kwargs):
        """Initialize with dynamic attributes from keyword arguments."""
        self._columns = set()
        self._data = {}
        
        # Set attributes dynamically
        for key, value in kwargs.items():
            self.set_attribute(key, value)
    
    def set_attribute(self, name: str, value: Any):
        """Set an attribute with automatic type handling."""
        # Clean column name (remove spaces, special chars)
        clean_name = self._clean_column_name(name)
        
        # Store original and cleaned names
        self._columns.add(clean_name)
        self._data[clean_name] = {
            'original_name': name,
            'value': self._convert_value(value),
            'type': type(value).__name__
        }
        
        # Set as instance attribute
        setattr(self, clean_name, self._data[clean_name]['value'])
    
    def _clean_column_name(self, name: str) -> str:
        """Convert column name to valid Python attribute name."""
        # Replace spaces and special characters with underscores
        clean = ''.join(c if c.isalnum() else '_' for c in str(name))
        # Ensure it doesn't start with a number
        if clean and clean[0].isdigit():
            clean = f"col_{clean}"
        return clean.lower()
    
    def _convert_value(self, value: Any) -> Any:
        """Convert value to appropriate Python type."""
        if pd.isna(value):
            return None
        elif isinstance(value, (int, float, str, bool)): # for primitive types
            return value
        elif isinstance(value, Dict): ## for iterable types 
            return value
        else:
            return str(value)
    
    def get_attribute(self, name: str) -> Any:
        """Get attribute value by original or cleaned name."""
        clean_name = self._clean_column_name(name)
        if clean_name in self._data:
            return self._data[clean_name]['value']
        return None
    
    def get_original_column_name(self, cleaned_name: str) -> str:
        """Get original column name from cleaned name."""
        if cleaned_name in self._data:
            return self._data[cleaned_name]['original_name']
        return cleaned_name
    
    def to_dict(self, use_original_names: bool = True) -> Dict[str, Any]:
        """Convert model to dictionary."""
        if use_original_names:
            return {
                self._data[key]['original_name']: self._data[key]['value']
                for key in self._columns
            }
        else:
            return {key: self._data[key]['value'] for key in self._columns}
    
    def to_json(self, use_original_names: bool = True) -> str:
        """Convert model to JSON string."""
        return json.dumps(self.to_dict(use_original_names), default=str)
    
    def update(self, **kwargs):
        """Update multiple attributes at once."""
        for key, value in kwargs.items():
            self.set_attribute(key, value)
    
    def has_column(self, name: str) -> bool:
        """Check if column exists (by original or cleaned name)."""
        clean_name = self._clean_column_name(name)
        return clean_name in self._columns
    
    def get_columns(self) -> List[str]:
        """Get list of all original column names."""
        return [self._data[key]['original_name'] for key in self._columns]
    
    def __repr__(self):
        """String representation of the model."""
        attrs = []
        for key in sorted(self._columns):
            original_name = self._data[key]['original_name']
            value = self._data[key]['value']
            attrs.append(f"{original_name}={repr(value)}")
        return f"DynamicExcelModel({', '.join(attrs)})"
    
    def __str__(self):
        """Human-readable string representation."""
        return self.to_json(use_original_names=True)