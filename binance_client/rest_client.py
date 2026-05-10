from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self

import httpx
from pydantic import SecretStr
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from binance_client.errors import BinanceAPIError, BinanceNetworkError, BinanceRateLimitError
from binance_client.signing import with_signature


class BinanceRestClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: SecretStr | str | None = None,
        api_secret: SecretStr | str | None = None,
        recv_window: int = 5000,
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        self.api_secret = (
            api_secret.get_secret_value() if isinstance(api_secret, SecretStr) else api_secret
        )
        self.recv_window = recv_window
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.25, min=0.25, max=2),
        retry=retry_if_exception_type(BinanceNetworkError),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        signed: bool = False,
        auth: bool = False,
    ) -> dict[str, Any] | list[Any]:
        request_params: dict[str, Any] = {
            key: value
            for key, value in dict(params or {}).items()
            if value is not None and value != ""
        }
        headers: dict[str, str] = {}
        if signed:
            if not self.api_secret:
                raise BinanceAPIError(-2015, "Missing Binance API secret")
            request_params = with_signature(
                request_params, secret=self.api_secret, recv_window=self.recv_window
            )
            auth = True
        if auth:
            if not self.api_key:
                raise BinanceAPIError(-2015, "Missing Binance API key")
            headers["X-MBX-APIKEY"] = self.api_key
        params_for_http: Mapping[str, Any] | list[tuple[str, Any]] = (
            list(request_params.items()) if signed else request_params
        )
        try:
            response = await self._client.request(
                method.upper(), path, params=params_for_http, headers=headers
            )
        except httpx.HTTPError as exc:
            raise BinanceNetworkError(str(exc)) from exc

        if response.status_code in {418, 429}:
            payload = _safe_json(response)
            raise BinanceRateLimitError(
                int(payload.get("code", -1003)),
                str(payload.get("msg", "Rate limit exceeded")),
                status_code=response.status_code,
                retry_after=_retry_after(response),
            )
        if response.status_code >= 400:
            payload = _safe_json(response)
            raise BinanceAPIError(
                int(payload.get("code", response.status_code)),
                str(payload.get("msg", response.text)),
                status_code=response.status_code,
            )
        if not response.content:
            return {}
        return response.json()

    async def get_exchange_info(self) -> dict[str, Any]:
        data = await self._request("GET", "/v3/exchangeInfo")
        return dict(data)

    async def ping(self) -> dict[str, Any]:
        data = await self._request("GET", "/v3/ping")
        return dict(data)

    async def get_time(self) -> dict[str, Any]:
        data = await self._request("GET", "/v3/time")
        return dict(data)

    async def get_account(self) -> dict[str, Any]:
        data = await self._request("GET", "/v3/account", signed=True)
        return dict(data)

    async def get_symbol_price(self, symbol: str) -> dict[str, Any]:
        data = await self._request("GET", "/v3/ticker/price", params={"symbol": symbol.upper()})
        return dict(data)

    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        *,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[list[Any]]:
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit,
            "startTime": start_time_ms,
            "endTime": end_time_ms,
        }
        data = await self._request("GET", "/v3/klines", params=params)
        return list(data)

    async def new_order(self, **params: Any) -> dict[str, Any]:
        data = await self._request("POST", "/v3/order", params=params, signed=True)
        return dict(data)

    async def test_order(self, **params: Any) -> dict[str, Any]:
        data = await self._request("POST", "/v3/order/test", params=params, signed=True)
        return dict(data)

    async def cancel_order(self, symbol: str, order_id: int | str) -> dict[str, Any]:
        data = await self._request(
            "DELETE",
            "/v3/order",
            params={"symbol": symbol.upper(), "orderId": order_id},
            signed=True,
        )
        return dict(data)

    async def get_order(self, symbol: str, order_id: int | str) -> dict[str, Any]:
        data = await self._request(
            "GET",
            "/v3/order",
            params={"symbol": symbol.upper(), "orderId": order_id},
            signed=True,
        )
        return dict(data)


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {"code": response.status_code, "msg": response.text}
    return payload if isinstance(payload, dict) else {"code": response.status_code, "msg": payload}


def _retry_after(response: httpx.Response) -> int | None:
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None
