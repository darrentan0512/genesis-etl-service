from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from app import mongo
from app.config import Config
from app.models.error_response import UpstreamError
from app.routes.schedule_config import (
    convert_request_to_mongo_format,
    generate_13_digit_uid_fixed,
    validate_schedule_config,
)
from app.services.engine_client.client_request import (
    run_engine_client,  # your function that raises UpstreamError
)
from app.services.engine_client.validate_and_format_schedule import (
    validate_and_format_schedule,
)
from app.utils.calculating_shift import (
    calculate_total_time_blocks,
    generate_time_unit_map,
    get_time_unit_from_datetime_and_time,
    inverse_map,
    store_time_mapping_safely,
)

# from app.validators.engine import validate_engine_response

scheduling_bp = Blueprint("scheduling", __name__, url_prefix="/api/scheduling")


@scheduling_bp.app_errorhandler(UpstreamError)
def handle_upstream_error(e: UpstreamError):
    """
    Consistent error response formatting for UpstreamError.
    Ensures `success` is always False and structure matches other API responses.
    """
    current_app.logger.error(e.to_logs())

    return e.to_response()


@scheduling_bp.app_errorhandler(BadRequest)
def handle_bad_request(e: BadRequest):
    """
    ### BadRequest handler
    Keeps JSON parsing errors consistent across routes in this blueprint.
    """
    return jsonify({"success": False, "message": "Invalid JSON body"}), 400


@scheduling_bp.app_errorhandler(UnsupportedMediaType)
def handle_unsupported_media(e: UnsupportedMediaType):
    """
    ### UnsupportedMediaType handler
    Ensures wrong content types return a stable JSON error.
    """
    return jsonify(
        {"success": False, "message": "Content-Type must be application/json"}
    ), 415



def create_schedule_config(
    schedule_uuid: str, schedule_period: dict[str, str], company: str, department: str
):
    start_date_str, end_date_str, start_time_str, end_time_str = (
        schedule_period["start_date"],
        schedule_period["end_date"],
        schedule_period["start_time"],
        schedule_period["end_time"],
    )

    start_dt, end_dt = (
        datetime.strptime(f"{start_date_str} {start_time_str}", "%Y-%m-%d %H:%M"),
        datetime.strptime(f"{end_date_str} {end_time_str}", "%Y-%m-%d %H:%M"),
    )

    # Generate mappings based on start and end planning horizon
    time_block_horus = 0.5
    total_time_blocks = calculate_total_time_blocks(start_dt, end_dt, time_block_horus)
    time_unit_map = generate_time_unit_map(start_dt, end_dt, time_block_horus)
    datetime_to_unit_map = inverse_map(time_unit_map)
    store_time_mapping_safely(
        schedule_uuid, time_unit_map, datetime_to_unit_map, department, company
    )

    shift_obj = mongo.db.configs.find(
        {"DEPARTMENT": department, "COMPANY": company}, {"SHIFT_TYPE": 1, "_id": 0}
    ).next()
    shifts = shift_obj.get("SHIFT_TYPE", [])

    mongo_shifts = []
    for shift in shifts:
        shift_type = shift["type"]
        roles_applied_to = shift["roles_applied_to"]
        days_applied_to = shift["days_applied_to"]

        start_tbs, end_tbs = _get_shift_start_end_tbs(
            shift, start_dt, end_dt, datetime_to_unit_map
        )

        shift_uid = generate_13_digit_uid_fixed()
        mongo_shift = {
            "shift_uid": shift_uid,
            "start_time_block": start_tbs,
            "type": shift_type,
            "end_time_block": end_tbs,
            "roles_applied_to": roles_applied_to,
            "days_applied_to": days_applied_to,
        }
        print(f"Mongo_SHIFT: {mongo_shift}")
        mongo_shifts.append(mongo_shift)

    # Build the final MongoDB document
    mongo_doc = {
        "schedule_uuid": schedule_uuid,
        "scheduling_period": {
            "start_date": start_date_str,
            "end_date": end_date_str,
            "start_time": start_time_str,
            "end_time": end_time_str,
            "number_of_days": schedule_period["number_of_days"],
            "total_time_block": total_time_blocks,
        },
        "COMPANY": company,
        "DEPARTMENT": department,
        "SHIFT": mongo_shifts,
    }

    return mongo_doc


def _get_shift_start_end_tbs(
    shift: dict[str, Any],
    start_datetime: datetime,
    end_datetime: datetime,
    datetime_to_unit_map: dict[datetime, int],
):
    start_time, end_time = shift["start_time"], shift["end_time"]
    start_time_dt, end_time_dt = (
        datetime.strptime(start_time, "%H:%M"),
        datetime.strptime(end_time, "%H:%M"),
    )

    days_applied_to = shift["days_applied_to"]

    start_tbs, end_tbs = [], []
    current_datetime = start_datetime
    # Iterate throw all days to generate timeblocks
    while current_datetime <= end_datetime:
        if current_datetime.weekday() in days_applied_to:
            shift_start_dt = datetime.combine(
                current_datetime.date(), start_time_dt.time()
            )
            shift_end_dt = datetime.combine(current_datetime.date(), end_time_dt.time())

            # check if shift_end_dt < shift_start_dt, if so, account for cross day end time
            if shift_end_dt <= shift_start_dt:
                shift_end_dt += timedelta(days=1)

            start_tbs.append(datetime_to_unit_map[shift_start_dt])
            end_tbs.append(datetime_to_unit_map[shift_end_dt])

        print(f"currentdt: {current_datetime}")
        current_datetime += timedelta(days=1)

    return start_tbs, end_tbs

@scheduling_bp.route("/generate", methods=["POST"])
def generate_and_save_schedule():
    """
    ### Generate schedule
    Validates request JSON, calls the engine upstream, verifies the engine response contract,
    and returns the normalized result.

    **Errors surfaced**
    - 415 if `Content-Type` is not JSON
    - 400 for invalid/malformed JSON or non-object payloads
    - Any upstream failures are raised by `run_engine_client` and normalized by `handle_upstream_error`
    - 502 if the engine response fails your contract checks
    """
    # quick content-type guard (will be turned into a 415 JSON by the handler)
    if not request.is_json:
        raise UnsupportedMediaType()

    payload = request.get_json(silent=False)  # raises BadRequest if fails
    if not isinstance(payload, dict):
        return jsonify({"success": False, "message": "Body must be a JSON object"}), 400

    url = f"{Config.ENGINE_BASE_URL}{Config.ENGINE_PATH}"
    token = Config.ENGINE_TOKEN
    timeout = Config.ENGINE_TIMEOUT

    # Manipulate shift information to format for engine
    schedule_uuid = str(uuid.uuid4())
    try:
        mongo_doc = create_schedule_config(
            schedule_uuid,
            payload["SCHEDULING_PERIOD"],
            payload["COMPANY"],
            payload["DEPARTMENT"],
        )
    except Exception as e:
        return jsonify(
            {
                "success": False,
                "message": "Error converting request data",
                "error": str(e),
            }
        ), 400

    # Add timestamps
    mongo_doc["updated_at"] = datetime.now(timezone.utc)
    mongo_doc["created_at"] = datetime.now(timezone.utc)

    # Updated schedule config info if needed
    query_filter = {"DEPARTMENT": payload["DEPARTMENT"], "COMPANY": payload["COMPANY"]}
    update_doc = {"$set": {**mongo_doc}}
    result = mongo.db.schedule_config.update_one(query_filter, update_doc, upsert=True)

    if result.upserted_id:
        print(f"Updated schedule configuration. Upserted id: {result.upserted_id}")
    else:
        print("No document to update!")

    # Add schedule_uuid into payload for engine referencing
    payload["schedule_uuid"] = schedule_uuid
    schedule: Any = run_engine_client(url, payload, token=token, timeout=timeout)

    # enforce for now while engine is still unstable
    errs = validate_and_format_schedule(schedule)
    if errs:
        current_app.logger.warning("InvalidEngineResponse", extra={"errors": errs})

        return jsonify(
            {
                "success": False,
                "message": "Invalid engine response",
                "error": "Engine response did not satisfy contract",
                "validation_errors": errs,  # structured list for programmatic use
            }
        ), 502

    schedule_to_store = {
        **schedule,
        "schedule_uuid": schedule_uuid,
        "COMPANY": payload["COMPANY"],
        "DEPARTMENT": payload["DEPARTMENT"],
    }
    mongo.db.schedules.insert_one(schedule_to_store)

    # pop storage _id from schedule, not needed as uuid is "entry_uuid"
    schedule_to_store.pop("_id", None)
    response = {
        "success": True,
        "message": "Schedule generated",
        **schedule_to_store,
    }
    return jsonify(response), 200


@scheduling_bp.route("/get_schedules", methods=["GET"])
def get_schedules():
    # Required headers (same contract you had)
    company = request.headers.get("COMPANY")
    department = request.headers.get("DEPARTMENT")
    if not company or not department:
        return jsonify(
            {
                "success": False,
                "message": "Missing required headers 'COMPANY' and 'DEPARTMENT'",
            }
        ), 400

    # Optional filter via query param: ?schedule_uuid=abc or ?schedule_uuid=a,b,c
    schedule_uuid_param = request.args.get("schedule_uuid", "").strip()

    filter_doc = {"COMPANY": company, "DEPARTMENT": department}
    if schedule_uuid_param:
        uuids = [u.strip() for u in schedule_uuid_param.split(",") if u.strip()]
        if len(uuids) == 1:
            filter_doc["schedule_uuid"] = uuids[0]
        elif uuids:
            filter_doc["schedule_uuid"] = {"$in": uuids}

    # Same projection, same response shape
    cursor = mongo.db.schedules.find(filter_doc, {"_id": 0})
    return jsonify({"success": True, "schedules": list(cursor)}), 200