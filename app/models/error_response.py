from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from flask import jsonify, request


@dataclass
class ErrorResponse(Exception):
    title: str
    status: int
    detail: str
    error_type: str = "validation-failed"
    errors: Dict[str, str] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    instance: Optional[str] = field(default=None)

    def __post_init__(self):
        if not self.instance and request:
            self.instance = f"uri={request.path}"
        self.type = f"https://api.domain.com/errors/{self.error_type}"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("error_type", None)  # Remove internal field
        return {k: v for k, v in data.items() if v is not None}

    def to_response(self):
        return jsonify(self.to_dict()), self.status


class UpstreamError(Exception):
    """
    Raised for non-2xx responses or transport failures when connecting
    to scheduling engine.
    """

    _MESSAGE_MAP = {
        400: "Upstream error: Bad request",
        401: "Upstream error: Unauthorized",
        403: "Upstream error: Forbidden",
        404: "Upstream error: Resource not found",
        409: "Upstream error: Conflict",
        422: "Upstream error: Unprocessable entity",
        429: "Upstream error: Too many requests",
        502: "Upstream error: Bad gateway",
        503: "Upstream error: Service unavailable",
        504: "Upstream error: Gateway timed out",
    }

    def __init__(
        self,
        status: int,
        error: str | None = None,
        *,
        raw_upstream: object | None = None,
    ):
        """
        Args:
            status: HTTP status code to return.
            error_detail: Raw technical error detail (e.g., str(e) from requests).
            details: Optional structured data from the upstream.
        """
        self.status = status
        self.body = {
            "success": False,
            "message": self._MESSAGE_MAP.get(
                status,
                "Upstream error: Server error"
                if 500 <= status < 600
                else "Upstream error",
            ),
        }

        if error:
            self.body["error"] = error  # if required to return to frontend

        self.raw_upstream = raw_upstream
        super().__init__(f"{status}: {self.body['message']}")
