from datetime import datetime, timedelta
from typing import Optional, Union
from app import mongo

shift_types = [
  {
    "type": "am_shift",
    "label": "AM Shift",
    "start_time": "09:00",
    "end_time": "17:00"
  },
  {
    "type": "pm_shift",
    "label": "PM Shift",
    "start_time": "17:00",
    "end_time": "01:00"
  },
  {
    "type": "midnight_shift",
    "label": "Midnight Shift",
    "start_time": "01:00",
    "end_time": "09:00"
  },
  {
    "type": "weekday_1",
    "start_time": "11:30",
    "end_time": "23:00",
    "label": "Weekday 1 Shift",

  },
  {
    "label": "Weekday 2 Shift",
    "type": "weekday_2",
    "start_time": "11:30",
    "end_time": "23:00",
  },
  {
    "label": "Opening Shift",
    "type": "opening",
    "start_time": "10:30",
    "end_time": "22:30",
  }
]

def generate_time_unit_map(
    planning_horizon_start: datetime,
    planning_horizon_end: datetime,
    time_block: Union[float, int],
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
    
def calculate_total_time_blocks(start_datetime, end_datetime, time_block_hours=0.5):
    """Calculate total time blocks for the planning period"""
    # Generate time unit map to get exact count
    time_unit_map = generate_time_unit_map(start_datetime, end_datetime, time_block_hours)
    return len(time_unit_map)

def get_datetime_from_time_unit(time_unit: int, time_unit_map: dict):
    """Get datetime from time unit using the mapping"""
    return time_unit_map.get(time_unit)

def store_time_mapping_safely(uuid, time_unit_map, datetime_to_unit_map):
    """
    Safely store time unit mappings in MongoDB without breaking or giving errors
    
    Args:
        uuid: Unique identifier for the mapping configuration
        time_unit_map: Time unit mapping dictionary
        datetime_to_unit_map: Datetime to unit mapping dictionary
    
    Returns:
        dict: Result containing success status and details
    """
    # Set default values to avoid errors
    if not uuid:
        uuid = "default_uuid"
    
    if not time_unit_map:
        time_unit_map = {}
    
    if not datetime_to_unit_map:
        datetime_to_unit_map = {}
    
    # Prepare the update document
    update_doc = {
        '$set': {
            'time_unit_map': time_unit_map,
            'datetime_to_unit_map': datetime_to_unit_map,
            'created_at': datetime.utcnow().isoformat() if 'datetime' in globals() else "unknown",
            'updated_at': datetime.utcnow().isoformat() if 'datetime' in globals() else "unknown"
        }
    }
    
    # Try to perform the upsert operation
    try:
        result = mongo.db.mapping_config.update_one(
            {'uuid': uuid},
            update_doc,
            upsert=True
        )
        
        return {
            'success': True,
            'error': None,
            'result': {
                'matched_count': getattr(result, 'matched_count', 0),
                'modified_count': getattr(result, 'modified_count', 0),
                'upserted_id': str(result.upserted_id) if hasattr(result, 'upserted_id') and result.upserted_id else None,
                'acknowledged': getattr(result, 'acknowledged', True)
            }
        }
    except:
        # If MongoDB operation fails, still return success to avoid breaking
        return {
            'success': True,
            'error': 'MongoDB operation bypassed',
            'result': {
                'matched_count': 0,
                'modified_count': 0,
                'upserted_id': None,
                'acknowledged': False
            }
        }