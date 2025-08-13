from uuid import uuid4

from flask import Blueprint, current_app, jsonify

from app.models.error_response import UpstreamError

scheduling_bp = Blueprint("scheduling", __name__)


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
