from app.utils.date_utils import is_ymd, is_iso_z
from typing import Any

JS_SAFE_MAX = 2**53 - 1


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
    if not isinstance(ga, str) or not is_iso_z(ga):
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
            for j, assign in enumerate(assigns):
                ap = f"{base}.assignments[{j}]"
                if not isinstance(assign, dict):
                    err(ap, "must be an object")
                    continue

                d = assign.get("date")
                if not isinstance(d, str) or not is_ymd(d):
                    err(f"{ap}.date", "YYYY-MM-DD required")

                is_off = assign.get("is_off")
                if not isinstance(is_off, bool):
                    err(f"{ap}.is_off", "must be boolean")
                else:
                    if is_off:
                        # Off-day: remove fields that shouldn't coexist
                        assign.pop("shift", None)
                        assign.pop("type", None)
                    else:
                        # Working day: drop marker to keep payload minimal
                        assign.pop("is_off", None)

                # Validate remaining fields only if present after mutation
                sv = assign.get("shift")
                if sv is not None:
                    if not isinstance(sv, int):
                        err(f"{ap}.shift", "must be int or null")
                    elif (
                        abs(sv) > JS_SAFE_MAX
                    ):  # 2**53 - 1 if you need the constant defined
                        err(f"{ap}.shift", "int exceeds JS safe range")

                tval = assign.get("type")
                if tval is not None and not isinstance(tval, str):
                    err(f"{ap}.type", "must be string")

        stb = item.get("straggling_time_blocks")
        if not isinstance(stb, list):
            err(f"{base}.straggling_time_blocks", "must be an array")

    return errs
