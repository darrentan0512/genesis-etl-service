from datetime import datetime
from typing import List, Dict

class Worker:
    """Worker model class - represents a single worker entity"""
    
    def __init__(self, name: str, skillset: str, probation: bool = False, leave_request: List[Dict[str, str]] = None):
        self.name = name
        self.skillset = skillset
        self.probation = probation
        self.leave_request = leave_request or []
    
    def to_dict(self) -> Dict:
        """Convert worker object to dictionary"""
        return {
            "name": self.name,
            "leave_request": self.leave_request,
            "skillset": self.skillset,
            "probation": self.probation
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Worker':
        """Create worker object from dictionary"""
        return cls(
            name=data.get("name"),
            skillset=data.get("skillset"),
            probation=data.get("probation", False),
            leave_request=data.get("leave_request", [])
        )
    
    def add_leave_request(self, start_date: str, end_date: str) -> None:
        """Add a leave request to this worker"""
        self.leave_request.append({"start": start_date, "end": end_date})
    
    def is_on_leave(self, check_date: str) -> bool:
        """Check if this worker is on leave on a specific date"""
        check_dt = datetime.strptime(check_date, "%d/%m/%Y")
        
        for leave in self.leave_request:
            start_dt = datetime.strptime(leave["start"], "%d/%m/%Y")
            end_dt = datetime.strptime(leave["end"], "%d/%m/%Y")
            
            if start_dt <= check_dt <= end_dt:
                return True
        return False
    
    def update_skillset(self, skillset: str) -> None:
        """Update worker's skillset"""
        self.skillset = skillset
    
    def set_probation_status(self, status: bool) -> None:
        """Set probation status"""
        self.probation = status
