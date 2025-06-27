from datetime import datetime, timezone
import uuid
from venv import logger
import pandas as pd
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
import json
from app import mongo
from app.config import Config  # Assuming Config is defined in app.config
from app.models.dynamic_worker import DynamicExcelModel
from app.models.error_response import ErrorResponse
from app.utils.validation_utils import COLUMN_VALIDATION_CONFIG

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
        'version': '1',
        'category': 'DEFAULT'
    }

    # Upsert column mapping into MongoDB for DEFAULT category
    try:
        collection = mongo.db.employee_column_mapping
        filter_query = {'category': 'DEFAULT'}
        update_query = {
            '$set': {
                'required_columns': required_columns,
                'non_required_columns': non_required_columns,
                'version': '1',
                'category': 'DEFAULT',
                'updated_at': datetime.now(timezone.utc)
            },
            '$setOnInsert': {
                'created_at': datetime.now(timezone.utc),
                'uuid': str(uuid.uuid4())
            }
        }
        result = collection.update_one(filter_query, update_query, upsert=True)
        
        if result.upserted_id:
            logger.info(f"Inserted new DEFAULT category column mapping with _id: {result.upserted_id}")
        else:
            logger.info(f"Updated existing DEFAULT category column mapping with matched_count: {result.matched_count}")
    except Exception as e:
        logger.error(f"Error upserting column mapping into MongoDB: {str(e)}")
        raise ErrorResponse(
            title="Database Error",
            status=500,
            detail="Failed to upsert column mapping into the database.",
            errors=str(e)
        )

class ExcelModelFactory:
    """Factory class to create DynamicExcelModel instances from Excel data."""
    
    @staticmethod
    def from_dataframe(df: Union[pd.DataFrame, Dict[str, pd.DataFrame]]) -> List[DynamicExcelModel]:
        """Create model instances from pandas DataFrame or dictionary of DataFrames."""
        if isinstance(df, pd.DataFrame):
            excel_models = ExcelModelFactory._process_single_dataframe(df)
            return excel_models
        elif isinstance(df, dict):
            models = []
            for sheet_name, sheet_df in df.items():
                if not isinstance(sheet_df, pd.DataFrame):
                    raise TypeError(f"Expected a DataFrame for sheet '{sheet_name}', but got {type(sheet_df)}")
                models.extend(ExcelModelFactory._process_single_dataframe(sheet_df))
            return models
        else:
            raise TypeError(f"Expected a DataFrame or dictionary of DataFrames, but got {type(df)}")

    @staticmethod
    def _process_single_dataframe(df: pd.DataFrame) -> List[DynamicExcelModel]:
        """Helper method to process a single DataFrame."""
        models = []
        for _, row in df.iterrows():
            model = DynamicExcelModel()
            additional_fields = {}
            for column, value in row.items():
                if value is not None and not pd.isna(value):
                    transformed_column = column.upper().replace(' ', '_')
                    if transformed_column.lower() in Config.MANDATORY_COLUMNS:
                        model.set_attribute(transformed_column, value)
                    else:
                        additional_fields[transformed_column] = value
            if len(additional_fields) > 0:
                model.set_attribute('ADDITIONAL_FIELDS', additional_fields)
            models.append(model)
        return models
    
    @staticmethod
    def from_excel_file(file_path: str) -> List[DynamicExcelModel]:
        """
        Create model instances directly from Excel file.
        Returns both the models and the column mapping.
        """
        # Read the Excel file
        df = pd.read_excel(file_path, engine="openpyxl")
        # Get original column names
        original_columns = list(df.columns)
        # Get required columns for validatio
        required_columns = [col['label'] for col in COLUMN_VALIDATION_CONFIG if col['required']]
        # Validate and create column mapping
        validate_store_columns(required_columns, original_columns)
        # Process the dataframe with the column mapping
        models = ExcelModelFactory.from_dataframe(df)
        
        return models
    
    @staticmethod
    def from_dict_list(data: List[Dict[str, Any]]) -> List[DynamicExcelModel]:
        """Create model instances from list of dictionaries."""
        return [DynamicExcelModel(**row) for row in data]

    @staticmethod
    def validate_columns(model_object: List[DynamicExcelModel]):
        mandatory_columns = [col['label'] for col in COLUMN_VALIDATION_CONFIG if col['required']]
        missing_columns = []
        for column in mandatory_columns:
            # Check if the column exists in the first model object
            if not model_object[0].has_column(column):
                missing_columns.append(column)
        if missing_columns:
                errors = [{"field": col, "message": f"{col} is required"} for col in missing_columns]
                raise ErrorResponse(
                    title="Validation Error",
                    status=400,
                    detail="Missing required fields.",
                    errors=errors
                )