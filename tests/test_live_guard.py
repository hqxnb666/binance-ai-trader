from __future__ import annotations

from decimal import Decimal

import pytest

from binance_client.errors import LiveTradingDisabledError
from broker.base import OrderRequest
from broker.binance_spot_live import BinanceSpotLiveBroker, require_live_enabled
from broker.binance_spot_testnet import BinanceSpotTestnetBroker
from broker.factory import create_broker
from config.settings import load_settings


@pytest.mark.asyncio
async def test_live_broker_place_order_fails_when_disabled() -> None:
    settings = load_settings().model_copy(
        update={"trading_mode": "live", "live_trading_enabled": False}
    )
    broker = BinanceSpotLiveBroker(settings)
    with pytest.raises(LiveTradingDisabledError):
        await broker.place_order(
            OrderRequest(
                symbol="BTCUSDT", side="BUY", quantity=Decimal("0.001"), price=Decimal("100")
            )
        )


def test_require_live_enabled_blocks_by_default() -> None:
    settings = load_settings().model_copy(
        update={"trading_mode": "live", "live_trading_enabled": False}
    )
    with pytest.raises(LiveTradingDisabledError):
        require_live_enabled(settings)


def test_testnet_mode_uses_testnet_broker() -> None:
    settings = load_settings().model_copy(update={"trading_mode": "testnet"})
    broker = create_broker(settings)
    assert isinstance(broker, BinanceSpotTestnetBroker)
