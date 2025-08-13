from json import JSONDecodeError
from typing import Optional

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

        # vaguely return, do not include full upstream error details
        raise UpstreamError(
            resp.status_code,
            resp.reason or "Upstream returned error",
            # upstream details are not parsed and returned but stored for logging
            raw_upstream=upstream,
        )

    # success 2xx response, but fail upon parsing the json
    try:
        return resp.json()
    except JSONDecodeError:
        raise UpstreamError(502, "Invalid JSON from upstream", raw_upstream=resp.text)
