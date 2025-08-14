from json import JSONDecodeError
from typing import Any, Optional

import requests

from app.models.error_response import UpstreamError


def run_engine_client(url: str, payload: dict, *, token: Optional[str], timeout: float):
    headers = {"Content-Type": "application/json"}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.post(url=url, json=payload, headers=headers, timeout=timeout)

    except requests.Timeout as e:
        raise UpstreamError(504, str(e))

    except requests.RequestException as e:
        raise UpstreamError(502, str(e))

    # non-2xx responses
    if not resp.ok:
        try:
            upstream = resp.json()
        except JSONDecodeError:
            # fall back to string if required
            upstream = resp.text

        raise UpstreamError(
            resp.status_code, "Upstream Error", raw_upstream=_cap(upstream)
        )

    # success 2xx response, but fail upon parsing the json
    try:
        return resp.json()
    except JSONDecodeError:
        raise UpstreamError(
            502, "Invalid JSON from upstream", raw_upstream=_cap(resp.text)
        )


def _cap(obj: Any, limit: int = 2000) -> Any:
    """Truncate large strings for log-friendliness; leave JSON objects/lists as-is."""
    if isinstance(obj, str) and len(obj) > limit:
        return obj[:limit] + "…"
    return obj
