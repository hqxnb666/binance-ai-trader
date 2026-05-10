from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Mapping
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode


def current_timestamp_ms() -> int:
    return int(time.time() * 1000)


def normalize_binance_param(value: Any) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def clean_params(params: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(key): normalize_binance_param(value)
        for key, value in params.items()
        if value is not None and value != ""
    }


def canonical_query_string(params: Mapping[str, Any]) -> str:
    clean = clean_params(params)
    ordered = sorted(clean.items(), key=lambda item: item[0])
    return urlencode(ordered, doseq=True)


def sign_query_string(query_string: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def sign_hmac_sha256(params: Mapping[str, Any], secret: str) -> str:
    return sign_query_string(canonical_query_string(params), secret)


def build_signed_params(
    params: Mapping[str, Any],
    secret: str,
    *,
    timestamp_ms: int,
    recv_window: int | None,
) -> dict[str, str]:
    signed = clean_params(params)
    if recv_window is not None:
        signed["recvWindow"] = normalize_binance_param(recv_window)
    signed["timestamp"] = normalize_binance_param(timestamp_ms)
    ordered_pairs = sorted(signed.items(), key=lambda item: item[0])
    query_string = urlencode(ordered_pairs, doseq=True)
    ordered = dict(ordered_pairs)
    ordered["signature"] = sign_query_string(query_string, secret)
    return ordered


def with_signature(
    params: Mapping[str, Any],
    *,
    secret: str,
    recv_window: int = 5000,
    timestamp_ms: int | None = None,
) -> dict[str, str]:
    return build_signed_params(
        params,
        secret,
        timestamp_ms=timestamp_ms or current_timestamp_ms(),
        recv_window=recv_window,
    )
