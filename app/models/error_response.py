from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, Any
from datetime import datetime
from flask import request, jsonify

@dataclass
class ErrorResponse:
    title: str
    status: int
    detail: str
    error_type: str = "validation-failed"
    errors: Dict[str, str] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    instance: Optional[str] = field(default=None)
    
    def __post_init__(self):
        if not self.instance and request:
            self.instance = f"uri={request.path}"
        self.type = f"https://api.domain.com/errors/{self.error_type}"
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop('error_type', None)  # Remove internal field
        return {k: v for k, v in data.items() if v is not None}
    
    def to_response(self):
        return jsonify(self.to_dict()), self.status
