from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from http import HTTPStatus
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


@dataclass
class UpstreamError(Exception):
    """
    Raised for non-2xx responses or transport failures when connecting
    to scheduling engine.
    """

    status: int
    detail: str
    code: Optional[str] = field(default=None)  # optional machine code for clients
    # logs-only payload (not returned to clients)
    raw_upstream: Optional[Any] = field(default=None)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )

    def __str__(self) -> str:
        return f"{self.status} {self.message()} :: {self.detail}"

    def _message(self) -> str:
        try:
            phrase = HTTPStatus(self.status).phrase
        # in case custom status code
        except ValueError:
            phrase = "Unknown Status Sode"
        return f"Upstream error: {phrase}"

    def to_dict(self, *, for_logs: bool = False) -> Dict[str, Any]:
        """
        ### to_dict
        Build a dict representation.
        - When `for_logs=True`, include `detail` and `timestamp`.
        - When `for_logs=False`, omit those fields to avoid leaking internals.
        """
        data = asdict(self)
        if not for_logs:
            data.pop("detail", None)
            data.pop("timestamp", None)
            data.pop("raw_upstream")
        return {k: v for k, v in data.items() if v is not None}

    def to_response(self):
        """
        ### to_response
        Flask response for clients: stable, high-level shape.
        """
        body = {
            "success": False,
            "message": self._message(),
            **self.to_dict(for_logs=False),
        }
        return jsonify(body), self.status

    def to_logs(self) -> Dict[str, Any]:
        """
        ### to_logs
        Dict for server logs: includes technical detail & timestamp.
        """
        log_body = {
            "message": self._message(),
            **self.to_dict(for_logs=True),
        }
        return log_body
