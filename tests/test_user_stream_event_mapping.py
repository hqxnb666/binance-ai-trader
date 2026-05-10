from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from broker.base import Broker, OrderRequest, OrderResult
from journal.models import Base, OrderRecord, RuntimeEvent
from orders.order_manager import OrderManager
from orders.order_state import OrderState


class NoopBroker(Broker):
    async def get_account(self) -> dict[str, Any]:
        return {}

    async def get_exchange_info(self) -> dict[str, Any]:
        return {}

    async def get_klines(self, symbol: str, interval: str, limit: int) -> list[list[Any]]:
        return []

    async def place_order(self, order_request: OrderRequest) -> OrderResult:
        raise AssertionError("not used")

    async def cancel_order(self, symbol: str, order_id: int | str) -> dict[str, Any]:
        return {}

    async def get_order(self, symbol: str, order_id: int | str) -> dict[str, Any]:
        return {}


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)()


def test_execution_report_updates_order_and_records_fill() -> None:
    session = _session()
    order = OrderRecord(
        client_order_id="cid",
        symbol="BTCUSDT",
        side="BUY",
        order_type="LIMIT",
        price=Decimal("100"),
        quantity=Decimal("0.1"),
        status=OrderState.WAITING_USER_STREAM.value,
        trading_mode="testnet",
        strategy_name="ema_trend",
        strategy_version="v1.0",
    )
    session.add(order)
    session.flush()
    manager = OrderManager(broker=NoopBroker(), session=session, trading_mode="testnet")
    updated = manager.handle_user_stream_event(
        {
            "e": "executionReport",
            "c": "cid",
            "X": "PARTIALLY_FILLED",
            "x": "TRADE",
            "i": 100,
            "s": "BTCUSDT",
            "S": "BUY",
            "L": "100",
            "l": "0.1",
            "n": "0.01",
            "N": "USDT",
            "E": 1_700_000_000_000,
        }
    )
    assert updated is not None
    assert updated.status == OrderState.PARTIALLY_FILLED.value
    assert len(updated.executions) == 1


def test_account_and_unknown_user_events_are_persisted() -> None:
    session = _session()
    manager = OrderManager(broker=NoopBroker(), session=session, trading_mode="testnet")
    manager.handle_user_stream_event({"e": "outboundAccountPosition", "B": []})
    manager.handle_user_stream_event({"e": "mysteryEvent", "x": 1})
    events = session.scalars(select(RuntimeEvent)).all()
    assert [event.event_type for event in events] == ["outboundAccountPosition", "mysteryEvent"]
    assert events[1].severity == "WARNING"

