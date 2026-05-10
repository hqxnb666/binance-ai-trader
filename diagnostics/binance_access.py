from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx
import websockets

from diagnostics.network import (
    REGION_RESTRICTED,
    STATUS_OK,
    TIMEOUT,
    classify_exception,
    classify_http_status,
    safe_details,
)

GLOBAL_REST = "https://api.binance.com/api/v3"
TESTNET_REST = "https://testnet.binance.vision/api/v3"
GLOBAL_WS = "wss://stream.binance.com:9443/ws/btcusdt@kline_5m"
TESTNET_WS = "wss://stream.testnet.binance.vision/ws/btcusdt@kline_5m"


async def check_binance_global_rest() -> dict[str, Any]:
    return await _check_rest(GLOBAL_REST)


async def check_binance_testnet_rest() -> dict[str, Any]:
    return await _check_rest(TESTNET_REST)


async def check_binance_global_ws() -> dict[str, Any]:
    return await _check_ws(GLOBAL_WS)


async def check_binance_testnet_ws() -> dict[str, Any]:
    return await _check_ws(TESTNET_WS)


async def _check_rest(base: str) -> dict[str, Any]:
    start = time.perf_counter()
    endpoints = ["/ping", "/time", "/exchangeInfo?symbol=BTCUSDT"]
    async with httpx.AsyncClient(timeout=10.0) as client:
        for endpoint in endpoints:
            url = f"{base}{endpoint}"
            try:
                response = await client.get(url)
            except Exception as exc:  # noqa: BLE001
                return {
                    "status": classify_exception(exc),
                    "latency_ms": int((time.perf_counter() - start) * 1000),
                    "details": safe_details(str(exc)),
                }
            status = classify_http_status(response.status_code, response.text)
            if status != STATUS_OK:
                return {
                    "status": status,
                    "latency_ms": int((time.perf_counter() - start) * 1000),
                    "details": safe_details(response.text or f"HTTP {response.status_code}"),
                }
    return {
        "status": STATUS_OK,
        "latency_ms": int((time.perf_counter() - start) * 1000),
        "details": "REST ping/time/exchangeInfo succeeded",
    }


async def _check_ws(url: str) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        async with websockets.connect(url, open_timeout=10, ping_interval=5) as websocket:
            raw = await asyncio.wait_for(websocket.recv(), timeout=10)
            json.loads(raw)
            return {
                "status": STATUS_OK,
                "latency_ms": int((time.perf_counter() - start) * 1000),
                "details": "WebSocket received first kline message",
            }
    except TimeoutError:
        return {
            "status": TIMEOUT,
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "details": "WebSocket timed out before receiving a message",
        }
    except Exception as exc:  # noqa: BLE001
        status = classify_exception(exc)
        details = safe_details(str(exc))
        if "451" in details or "restricted" in details.lower():
            status = REGION_RESTRICTED
        return {
            "status": status,
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "details": details,
        }
