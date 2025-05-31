import pandas as pd
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
import json
from app.models.dynamic_worker import DynamicExcelModel

class ExcelModelFactory:
    """Factory class to create DynamicExcelModel instances from Excel data."""
    
    @staticmethod
    def from_dataframe(df: Union[pd.DataFrame, Dict[str, pd.DataFrame]]) -> List[DynamicExcelModel]:
        """Create model instances from pandas DataFrame or dictionary of DataFrames."""
        if isinstance(df, pd.DataFrame):
            return ExcelModelFactory._process_single_dataframe(df)
        elif isinstance(df, dict):
            models = []
            print(df.keys())
            for sheet_name, sheet_df in df.items():
                if not isinstance(sheet_df, pd.DataFrame):
                    raise TypeError(f"Expected a DataFrame for sheet '{sheet_name}', but got {type(sheet_df)}")
                models.extend(ExcelModelFactory._process_single_dataframe(sheet_df))
            print(models)
            return models
        else:
            raise TypeError(f"Expected a DataFrame or dictionary of DataFrames, but got {type(df)}")

    @staticmethod
    def _process_single_dataframe(df: pd.DataFrame) -> List[DynamicExcelModel]:
        """Helper method to process a single DataFrame."""
        models = []
        for _, row in df.iterrows():
            model = DynamicExcelModel()
            for column, value in row.items():
                model.set_attribute(column, value)
            models.append(model)
        return models
    
    @staticmethod
    def from_excel_file(file_path: str) -> List[DynamicExcelModel]:
        """Create model instances directly from Excel file."""
        df = pd.read_excel(file_path, sheet_name=None, engine="openpyxl")  # Read all sheets
        return ExcelModelFactory.from_dataframe(df)
    
    @staticmethod
    def from_dict_list(data: List[Dict[str, Any]]) -> List[DynamicExcelModel]:
        """Create model instances from list of dictionaries."""
        return [DynamicExcelModel(**row) for row in data]