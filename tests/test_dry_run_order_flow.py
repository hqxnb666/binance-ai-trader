from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from broker.base import Broker, OrderRequest, OrderResult
from journal.models import Base, RiskDecision
from orders.order_manager import OrderManager
from orders.order_state import OrderState
from strategies.base import StrategySignalPayload


class CountingBroker(Broker):
    def __init__(self) -> None:
        self.place_calls = 0
        self.test_calls = 0

    async def get_account(self) -> dict[str, Any]:
        return {}

    async def get_exchange_info(self) -> dict[str, Any]:
        return {}

    async def get_klines(self, symbol: str, interval: str, limit: int) -> list[list[Any]]:
        return []

    async def place_order(self, order_request: OrderRequest) -> OrderResult:
        self.place_calls += 1
        return OrderResult(
            symbol=order_request.symbol,
            order_id=1,
            client_order_id=order_request.client_order_id or "id",
            status="NEW",
            side=order_request.side,
            order_type=order_request.order_type,
            price=order_request.price,
            quantity=order_request.quantity,
            raw={},
        )

    async def test_order(self, order_request: OrderRequest) -> dict[str, Any]:
        self.test_calls += 1
        return {}

    async def cancel_order(self, symbol: str, order_id: int | str) -> dict[str, Any]:
        return {}

    async def get_order(self, symbol: str, order_id: int | str) -> dict[str, Any]:
        return {}


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)()


def _signal() -> StrategySignalPayload:
    return StrategySignalPayload(
        symbol="BTCUSDT",
        strategy_name="ema_trend",
        strategy_version="v1.0",
        timeframe="5m",
        side="BUY",
        signal_type="ENTRY_CANDIDATE",
        confidence=0.7,
        reason="test",
        raw_payload_json={},
    )


@pytest.mark.asyncio
async def test_dry_run_approved_never_calls_broker_place_order() -> None:
    session = _session()
    broker = CountingBroker()
    risk = RiskDecision(symbol="BTCUSDT", approved=True, reason="ok", risk_state_json={})
    session.add(risk)
    session.flush()
    manager = OrderManager(broker=broker, session=session, trading_mode="testnet")
    record = await manager.submit_order(
        signal=_signal(),
        risk_decision=risk,
        order_request=OrderRequest(
            symbol="BTCUSDT", side="BUY", quantity=Decimal("0.1"), price=Decimal("100")
        ),
        dry_run=True,
        order_execution_enabled=False,
        precheck_test_order=True,
    )
    assert record.status == OrderState.DRY_RUN_APPROVED.value
    assert broker.place_calls == 0
    assert broker.test_calls == 0


@pytest.mark.asyncio
async def test_dry_run_rejected_creates_rejected_virtual_order() -> None:
    session = _session()
    broker = CountingBroker()
    risk = RiskDecision(symbol="BTCUSDT", approved=False, reason="no", risk_state_json={})
    session.add(risk)
    session.flush()
    manager = OrderManager(broker=broker, session=session, trading_mode="testnet")
    record = await manager.submit_order(
        signal=_signal(),
        risk_decision=risk,
        order_request=OrderRequest(
            symbol="BTCUSDT", side="BUY", quantity=Decimal("0.1"), price=Decimal("100")
        ),
        dry_run=True,
        order_execution_enabled=False,
    )
    assert record.status == OrderState.DRY_RUN_REJECTED.value
    assert broker.place_calls == 0
