from __future__ import annotations

from broker.base import Broker
from broker.binance_spot_live import BinanceSpotLiveBroker
from broker.binance_spot_testnet import BinanceSpotTestnetBroker
from config.settings import Settings


def create_broker(settings: Settings) -> Broker:
    if settings.trading_mode == "live":
        return BinanceSpotLiveBroker(settings)
    return BinanceSpotTestnetBroker(settings)

