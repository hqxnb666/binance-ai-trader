from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from broker.base import Broker
from config.settings import load_settings
from journal.models import Base
from runtime.trading_daemon import TestnetTradingDaemon as TradingDaemon


class FakeBroker(Broker):
    async def get_account(self):
        return {}

    async def get_exchange_info(self):
        return {"symbols": []}

    async def get_klines(self, symbol, interval, limit):
        return []

    async def place_order(self, order_request):
        raise AssertionError("not used")

    async def cancel_order(self, symbol, order_id):
        return {}

    async def get_order(self, symbol, order_id):
        return {}


def _factory():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)


def test_runtime_health_contains_budget_status() -> None:
    daemon = TradingDaemon(
        settings=load_settings(),
        session_factory=_factory(),
        broker=FakeBroker(),
        poll_interval_seconds=0.01,
    )
    health = daemon.health().model_dump()
    assert "budget_status" in health
    assert health["budget_status"]["budget_guard_enabled"] is True
