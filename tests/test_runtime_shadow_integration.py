from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from broker.base import Broker
from config.settings import load_settings
from journal.models import Base
from runtime.trading_daemon import TestnetTradingDaemon as TradingDaemon
from shadow.schemas import ShadowDecisionType
from shadow.store import list_recent_shadow_decisions


class FakeBroker(Broker):
    async def get_account(self):
        return {}

    async def get_exchange_info(self):
        return {"symbols": []}

    async def get_klines(self, symbol, interval, limit):
        return []

    async def place_order(self, order_request):
        raise AssertionError("Shadow Mode must not place orders")

    async def cancel_order(self, symbol, order_id):
        return {}

    async def get_order(self, symbol, order_id):
        return {}


def _factory():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)


def test_runtime_health_contains_shadow_status() -> None:
    daemon = TradingDaemon(
        settings=load_settings(),
        session_factory=_factory(),
        broker=FakeBroker(),
    )
    health = daemon.health().model_dump(mode="json")
    assert "shadow_status" in health
    assert health["shadow_status"]["enabled"] is True


def test_dry_run_shadow_record_does_not_call_broker() -> None:
    factory = _factory()
    daemon = TradingDaemon(
        settings=load_settings(),
        session_factory=factory,
        broker=FakeBroker(),
        dry_run=True,
        order_execution_enabled=False,
    )
    with factory() as session:
        daemon._record_shadow(
            session,
            decision_type=ShadowDecisionType.WOULD_PLACE_ORDER,
            symbol="BTCUSDT",
            side="BUY",
            reason="test",
            reason_codes=["WOULD_PLACE_ORDER"],
            simulated_entry_price="100",
            simulated_quantity="0.1",
            simulated_notional="10",
        )
        assert len(list_recent_shadow_decisions(session)) == 1
