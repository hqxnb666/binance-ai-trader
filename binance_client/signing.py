from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlencode


def current_timestamp_ms() -> int:
    return int(time.time() * 1000)


def canonical_query_string(params: Mapping[str, Any]) -> str:
    clean = {key: value for key, value in params.items() if value is not None}
    ordered = sorted(clean.items(), key=lambda item: item[0])
    return urlencode(ordered, doseq=True)


def sign_hmac_sha256(params: Mapping[str, Any], secret: str) -> str:
    payload = canonical_query_string(params)
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def with_signature(
    params: Mapping[str, Any],
    *,
    secret: str,
    recv_window: int = 5000,
    timestamp_ms: int | None = None,
) -> dict[str, Any]:
    signed: dict[str, Any] = dict(params)
    signed.setdefault("recvWindow", recv_window)
    signed["timestamp"] = timestamp_ms or current_timestamp_ms()
    signed["signature"] = sign_hmac_sha256(signed, secret)
    return signed

