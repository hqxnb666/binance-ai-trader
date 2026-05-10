from __future__ import annotations

from urllib.parse import parse_qsl

import httpx
import pytest

from binance_client.errors import BinanceAPIError
from binance_client.rest_client import BinanceRestClient


def _query_params(request: httpx.Request) -> dict[str, str]:
    query = request.url.query
    raw = query.decode("utf-8") if isinstance(query, bytes) else query
    return dict(parse_qsl(raw, keep_blank_values=True))


@pytest.mark.asyncio
async def test_get_account_sends_api_key_and_signed_query_params() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["headers"] = request.headers
        seen["params"] = _query_params(request)
        return httpx.Response(200, json={"balances": []})

    client = _mock_client(handler)
    try:
        await client.get_account()
    finally:
        await client.aclose()
    params = seen["params"]
    assert seen["path"] == "/api/v3/account"
    assert seen["headers"]["X-MBX-APIKEY"] == "key"
    assert {"timestamp", "recvWindow", "signature"} <= set(params)


@pytest.mark.asyncio
async def test_test_order_uses_order_test_endpoint_query_params_and_no_json_body() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["params"] = _query_params(request)
        seen["content"] = request.content
        return httpx.Response(200, json={})

    client = _mock_client(handler)
    try:
        await client.test_order(
            symbol="BTCUSDT",
            side="BUY",
            type="LIMIT",
            quantity="0.001",
            price="10000.00",
            timeInForce="GTC",
        )
    finally:
        await client.aclose()
    params = seen["params"]
    assert seen["method"] == "POST"
    assert seen["path"] == "/api/v3/order/test"
    assert seen["content"] == b""
    assert params["symbol"] == "BTCUSDT"
    assert params["side"] == "BUY"
    assert params["type"] == "LIMIT"
    assert params["quantity"] == "0.001"
    assert params["price"] == "10000.00"
    assert params["timeInForce"] == "GTC"
    assert {"timestamp", "recvWindow", "signature"} <= set(params)


@pytest.mark.asyncio
async def test_signed_error_1022_is_preserved_without_leaking_secret() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(
            400,
            json={"code": -1022, "msg": "Signature for this request is not valid."},
        )

    client = _mock_client(handler)
    with pytest.raises(BinanceAPIError) as exc_info:
        try:
            await client.test_order(symbol="BTCUSDT", side="BUY", type="LIMIT", quantity="1")
        finally:
            await client.aclose()
    assert exc_info.value.code == -1022
    assert "secret" not in str(seen["url"])
    assert "/api/v3/order/test" in str(seen["url"])
    assert "/api/v3/order?" not in str(seen["url"])


def _mock_client(handler) -> BinanceRestClient:
    client = BinanceRestClient(
        base_url="https://example.test/api",
        api_key="key",
        api_secret="secret",
    )
    client._client = httpx.AsyncClient(  # noqa: SLF001 - test injects transport
        base_url="https://example.test/api",
        transport=httpx.MockTransport(handler),
    )
    return client
