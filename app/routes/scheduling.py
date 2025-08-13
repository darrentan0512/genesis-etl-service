from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from app.config import Config
from app.models.error_response import UpstreamError
from app.services.engine_client.client_request import (
    run_engine_client,  # your function that raises UpstreamError
)
from app.services.engine_client.validate_and_format_schedule import (
    validate_and_format_schedule,
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


@scheduling_bp.route("/generate", methods=["POST"])
def generate_schedule():
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

    # UpstreamErrors raised will be handled by handler above
    schedule: Any = run_engine_client(url, payload, token=token, timeout=timeout)

    # enforce for now while engine is still unstabl
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

    return jsonify(
        {"success": True, "message": "Schedule generated", "data": schedule}
    ), 200
