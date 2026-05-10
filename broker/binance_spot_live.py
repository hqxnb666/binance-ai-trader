from __future__ import annotations

from typing import Any

from binance_client.errors import LiveTradingDisabledError
from binance_client.rest_client import BinanceRestClient
from broker.base import Broker, OrderRequest, OrderResult
from broker.binance_spot_testnet import _order_params, _order_result
from config.settings import Settings


def require_live_enabled(settings: Settings) -> None:
    if settings.trading_mode != "live":
        raise LiveTradingDisabledError("Trading mode is not live")
    if settings.live_trading.require_env_live_enabled and not settings.live_trading_enabled:
        raise LiveTradingDisabledError("LIVE_TRADING_ENABLED is not true")
    if settings.live_trading.require_manual_enable and not settings.live_trading.enabled:
        raise LiveTradingDisabledError("config live_trading.enabled is false")


class BinanceSpotLiveBroker(Broker):
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = BinanceRestClient(
            base_url=settings.binance_spot_live_rest_base,
            api_key=settings.binance_live_api_key,
            api_secret=settings.binance_live_api_secret,
        )

    async def get_account(self) -> dict[str, Any]:
        require_live_enabled(self.settings)
        return await self.client.get_account()

    async def get_exchange_info(self) -> dict[str, Any]:
        return await self.client.get_exchange_info()

    async def get_klines(self, symbol: str, interval: str, limit: int) -> list[list[Any]]:
        return await self.client.get_klines(symbol, interval, limit)

    async def place_order(self, order_request: OrderRequest) -> OrderResult:
        require_live_enabled(self.settings)
        raw = await self.client.new_order(**_order_params(order_request))
        return _order_result(raw, order_request)

    async def cancel_order(self, symbol: str, order_id: int | str) -> dict[str, Any]:
        require_live_enabled(self.settings)
        return await self.client.cancel_order(symbol, order_id)

    async def get_order(self, symbol: str, order_id: int | str) -> dict[str, Any]:
        require_live_enabled(self.settings)
        return await self.client.get_order(symbol, order_id)

