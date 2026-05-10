from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

STATUS_OK = "OK"
REGION_RESTRICTED = "REGION_RESTRICTED"
AUTH_ERROR = "AUTH_ERROR"
RATE_LIMITED = "RATE_LIMITED"
NETWORK_ERROR = "NETWORK_ERROR"
DNS_ERROR = "DNS_ERROR"
TLS_ERROR = "TLS_ERROR"
TIMEOUT = "TIMEOUT"
UNKNOWN_ERROR = "UNKNOWN_ERROR"

RESTRICTED_MARKERS = [
    "restricted location",
    "unavailable from your location",
    "service unavailable from a restricted location",
    "not available in your country",
    "http 451",
]


def classify_http_status(status_code: int, text: str) -> str:
    lowered = text.lower()
    if status_code == 451 or any(marker in lowered for marker in RESTRICTED_MARKERS):
        return REGION_RESTRICTED
    if status_code in {401, 403}:
        return AUTH_ERROR
    if status_code in {418, 429}:
        return RATE_LIMITED
    if status_code >= 500:
        return NETWORK_ERROR
    if status_code >= 400:
        return UNKNOWN_ERROR
    return STATUS_OK


def classify_exception(exc: BaseException) -> str:
    text = str(exc).lower()
    if any(marker in text for marker in RESTRICTED_MARKERS) or "451" in text:
        return REGION_RESTRICTED
    if isinstance(exc, TimeoutError | httpx.TimeoutException | asyncio.TimeoutError):
        return TIMEOUT
    if isinstance(exc, httpx.ConnectError) and ("name" in text or "dns" in text):
        return DNS_ERROR
    if "ssl" in text or "tls" in text or "certificate" in text:
        return TLS_ERROR
    if isinstance(exc, httpx.HTTPError | OSError):
        return NETWORK_ERROR
    return UNKNOWN_ERROR


def safe_details(text: str, max_len: int = 180) -> str:
    compact = " ".join(str(text).split())
    return compact[:max_len]


async def timed_check(fn: Callable[[], Awaitable[dict[str, Any]]]) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        result = await fn()
    except Exception as exc:  # noqa: BLE001 - diagnostics must classify instead of crash
        return {
            "status": classify_exception(exc),
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "details": safe_details(str(exc)),
        }
    result.setdefault("latency_ms", int((time.perf_counter() - start) * 1000))
    return result

