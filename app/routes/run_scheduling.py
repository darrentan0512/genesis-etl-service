from __future__ import annotations

from typing import Any
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from app.config import Config
from app.models.error_response import UpstreamError
from app.services.engine_client import (
    run_engine_client,  # your function that raises UpstreamError
)

# from app.validators.engine import validate_engine_response

scheduling_bp = Blueprint("scheduling", __name__, url_prefix="/api/scheduling")


@scheduling_bp.app_errorhandler(UpstreamError)
def handle_upstream_error(e: UpstreamError):
    """
    Consistent error response formatting for UpstreamError.
    Ensures `success` is always False and structure matches other API responses.
    """
    request_id = str(uuid4())

    # Log full upstream details internally
    current_app.logger.error(
        "upstream_error",
        extra={
            "request_id": request_id,
            "status": e.status,
            "raw_upstream": getattr(e, "raw_upstream", None),
        },
    )

    # Build consistent client-facing JSON
    return (
        jsonify(
            {
                "success": False,
                "message": e.body.get("message", "Upstream error"),
                "error": e.body.get("error", None),  # technical detail if available
            }
        ),
        e.status,
    )


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
