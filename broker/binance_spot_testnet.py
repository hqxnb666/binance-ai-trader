from __future__ import annotations

from decimal import Decimal
from typing import Any

from binance_client.rest_client import BinanceRestClient
from broker.base import Broker, OrderRequest, OrderResult
from config.settings import Settings


class BinanceSpotTestnetBroker(Broker):
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = BinanceRestClient(
            base_url=settings.binance_spot_testnet_rest_base,
            api_key=settings.binance_testnet_api_key,
            api_secret=settings.binance_testnet_api_secret,
        )

    async def get_account(self) -> dict[str, Any]:
        return await self.client.get_account()

    async def get_exchange_info(self) -> dict[str, Any]:
        return await self.client.get_exchange_info()

    async def get_klines(self, symbol: str, interval: str, limit: int) -> list[list[Any]]:
        return await self.client.get_klines(symbol, interval, limit)

    async def place_order(self, order_request: OrderRequest) -> OrderResult:
        params = _order_params(order_request)
        raw = await self.client.new_order(**params)
        return _order_result(raw, order_request)

    async def test_order(self, order_request: OrderRequest) -> dict[str, Any]:
        return await self.client.test_order(**_order_params(order_request))

    async def cancel_order(self, symbol: str, order_id: int | str) -> dict[str, Any]:
        return await self.client.cancel_order(symbol, order_id)

    async def get_order(self, symbol: str, order_id: int | str) -> dict[str, Any]:
        return await self.client.get_order(symbol, order_id)


def _order_params(order_request: OrderRequest) -> dict[str, Any]:
    params: dict[str, Any] = {
        "symbol": order_request.symbol,
        "side": order_request.side,
        "type": order_request.order_type,
        "quantity": format(order_request.quantity, "f"),
    }
    if order_request.client_order_id:
        params["newClientOrderId"] = order_request.client_order_id
    if order_request.order_type == "LIMIT":
        params["timeInForce"] = order_request.time_in_force
        if order_request.price is None:
            msg = "LIMIT order requires price"
            raise ValueError(msg)
        params["price"] = format(order_request.price, "f")
    return params


def _order_result(raw: dict[str, Any], fallback: OrderRequest) -> OrderResult:
    price = (
        Decimal(str(raw.get("price", fallback.price or "0")))
        if raw.get("price")
        else fallback.price
    )
    return OrderResult(
        symbol=str(raw.get("symbol", fallback.symbol)),
        order_id=raw.get("orderId"),
        client_order_id=str(raw.get("clientOrderId", fallback.client_order_id or "")),
        status=str(raw.get("status", "UNKNOWN")),
        side=str(raw.get("side", fallback.side)),
        order_type=str(raw.get("type", fallback.order_type)),
        price=price,
        quantity=Decimal(str(raw.get("origQty", fallback.quantity))),
        raw=raw,
    )
