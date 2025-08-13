from datetime import datetime
from typing import Any

JS_SAFE_MAX = 2**53 - 1


def _is_iso_z(dt_str: str) -> bool:
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


def _is_ymd(s: str) -> bool:
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


def validate_and_format_schedule(resp: dict) -> list[dict[str, Any]]:
    """
    Validate and normalize an engine schedule response **in a single pass**.

    Side effects:
        - Mutates `resp` in place:
          * When `is_off` is True: removes "shift" and "type" from each assignment.
          * When `is_off` is False: removes "is_off" from each assignment.

    Args:
        resp: Parsed JSON object from the engine. Expected shape:
              {
                "generated_at": "<ISO-8601 Z>",
                "data": [
                  {
                    "employee_id": "<str>",
                    "assignments": [
                      {
                        "date": "YYYY-MM-DD",
                        "is_off": <bool>,
                        "shift": <int|null>,
                        "type": "<str>"    # optional if is_off is True
                      }, ...
                    ],
                    "straggling_time_blocks": [ ... ]  # list
                  }, ...
                ]
              }

    Returns:
        List of validation errors, each as {"path": <json-path>, "error": <message>}.
        Empty list means no validation errors were found.
    """
    errs: list[dict[str, Any]] = []

    def err(path: str, msg: str) -> None:
        errs.append({"path": path, "error": msg})

    if not isinstance(resp, dict):
        return [{"path": "$", "error": "response must be an object"}]

    ga = resp.get("generated_at")
    if not isinstance(ga, str) or not _is_iso_z(ga):
        err("$.generated_at", "must be ISO-8601 string")

    data = resp.get("data")
    if not isinstance(data, list):
        err("$.data", "must be an array")
        return errs  # can't proceed

    for i, item in enumerate(data):
        base = f"$.data[{i}]"
        if not isinstance(item, dict):
            err(base, "must be an object")
            continue

        employee_id = item.get("employee_id")
        if not isinstance(employee_id, str):
            err(f"{base}.employee_id", "must be a string")

        assigns = item.get("assignments")
        if not isinstance(assigns, list):
            err(f"{base}.assignments", "must be an array")
        else:
            for j, a in enumerate(assigns):
                ap = f"{base}.assignments[{j}]"
                if not isinstance(a, dict):
                    err(ap, "must be an object")
                    continue

                d = a.get("date")
                if not isinstance(d, str) or not _is_ymd(d):
                    err(f"{ap}.date", "YYYY-MM-DD required")

                is_off = a.get("is_off")
                if not isinstance(is_off, bool):
                    err(f"{ap}.is_off", "must be boolean")
                else:
                    if is_off:
                        # Off-day: remove fields that shouldn't coexist
                        a.pop("shift", None)
                        a.pop("type", None)
                    else:
                        # Working day: drop marker to keep payload minimal
                        a.pop("is_off", None)

                # Validate remaining fields only if present after mutation
                sv = a.get("shift")
                if sv is not None:
                    if not isinstance(sv, int):
                        err(f"{ap}.shift", "must be int or null")
                    elif (
                        abs(sv) > JS_SAFE_MAX
                    ):  # 2**53 - 1 if you need the constant defined
                        err(f"{ap}.shift", "int exceeds JS safe range")

                tval = a.get("type")
                if tval is not None and not isinstance(tval, str):
                    err(f"{ap}.type", "must be string")

        stb = item.get("straggling_time_blocks")
        if not isinstance(stb, list):
            err(f"{base}.straggling_time_blocks", "must be an array")

    return errs
