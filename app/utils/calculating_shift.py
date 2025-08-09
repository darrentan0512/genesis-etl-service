from datetime import datetime, timedelta
from typing import Optional

shift_types = [
  {
    "type": "am_shift",
    "label": "AM Shift",
    "start_time": "09:00",
    "end_time": "17:00"
  },
  {
    "type": "pm_shift",
    "label": "AM Shift",
    "start_time": "17:00",
    "end_time": "01:00"
  },
  {
    "type": "midnight_shift",
    "label": "Midnight Shift",
    "start_time": "01:00",
    "end_time": "09:00"
  }
]

def generate_time_unit_map(
    planning_horizon_start: datetime,
    planning_horizon_end: datetime,
    time_block: float | int,
):
    """Generate a mapping from time units to datetime"""
    time_unit_map = {}
    current_time = planning_horizon_start
    current_time_unit = 0

    while current_time <= planning_horizon_end:
        time_unit_map[current_time_unit] = current_time
        current_time += timedelta(hours=time_block)
        current_time_unit += 1

    return time_unit_map


def inverse_map(map_dict: dict):
    """Inverses a dictionary flipping key and value pairs."""
    return {v: k for k, v in map_dict.items()}

def get_time_unit_from_datetime_and_time(date_str, time_str, datetime_to_unit_map):
    """
    Convert date string and time string to time unit
    Args:
        date_str: Date in YYYY-MM-DD format
        time_str: Time in HH:MM format
        datetime_to_unit_map: Mapping from datetime to time units
    Returns:
        Time unit number or None if not found
    """
    try:
        # Parse date and time
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        time_obj = datetime.strptime(time_str, '%H:%M').time()
        
        # Combine into datetime
        combined_datetime = datetime.combine(date_obj, time_obj)
        
        # Look up time unit
        return datetime_to_unit_map.get(combined_datetime)
    except:
        return None
    
def calculate_total_time_blocks(start_date_str, end_date_str, time_block_hours=0.5):
    """Calculate total time blocks for the planning period"""
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    
    # Generate time unit map to get exact count
    time_unit_map = generate_time_unit_map(start_date, end_date, time_block_hours)
    return len(time_unit_map)

def get_datetime_from_time_unit(time_unit: int, time_unit_map: dict):
    """Get datetime from time unit using the mapping"""
    return time_unit_map.get(time_unit)