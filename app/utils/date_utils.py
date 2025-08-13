from datetime import datetime
from typing import Any


def is_iso_z(dt_str: str) -> bool:
    """
    Check if a string is a valid ISO-8601 date-time with 'Z' for UTC.

    Args:
        dt_str: Date-time string to validate.

    Returns:
        True if valid, False otherwise.
    """
    try:
        datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return True
    except Exception:
        return False


def is_ymd(s: str) -> bool:
    """
    Check if a string is in YYYY-MM-DD format.

    Args:
        s: Date string to validate.

    Returns:
        True if valid, False otherwise.
    """
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except Exception:
        return False

