import pandas as pd
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
import json
from app.models.dynamic_worker import DynamicExcelModel

class ExcelModelFactory:
    """Factory class to create DynamicExcelModel instances from Excel data."""
    
    @staticmethod
    def from_dataframe(df: pd.DataFrame) -> List[DynamicExcelModel]:
        """Create model instances from pandas DataFrame."""
        models = []
        for _, row in df.iterrows():
            model = DynamicExcelModel()
            for column, value in row.items():
                model.set_attribute(column, value)
            models.append(model)
        return models
    
    @staticmethod
    def from_excel_file(file_path: str, sheet_name: Optional[str] = None) -> List[DynamicExcelModel]:
        """Create model instances directly from Excel file."""
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        return ExcelModelFactory.from_dataframe(df)
    
    @staticmethod
    def from_dict_list(data: List[Dict[str, Any]]) -> List[DynamicExcelModel]:
        """Create model instances from list of dictionaries."""
        return [DynamicExcelModel(**row) for row in data]