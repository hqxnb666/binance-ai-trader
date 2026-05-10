from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from binance_client.errors import RiskRejectedError
from broker.base import Broker, OrderRequest, OrderResult
from journal.models import Base, RiskDecision
from orders.order_manager import OrderManager
from orders.order_state import OrderState
from strategies.base import StrategySignalPayload


class FakeBroker(Broker):
    def __init__(self) -> None:
        self.calls = 0

    async def get_account(self) -> dict[str, Any]:
        return {}

    async def get_exchange_info(self) -> dict[str, Any]:
        return {}

    async def get_klines(self, symbol: str, interval: str, limit: int) -> list[list[Any]]:
        return []

    async def place_order(self, order_request: OrderRequest) -> OrderResult:
        self.calls += 1
        return OrderResult(
            symbol=order_request.symbol,
            order_id=123,
            client_order_id=order_request.client_order_id or "missing",
            status="NEW",
            side=order_request.side,
            order_type=order_request.order_type,
            price=order_request.price,
            quantity=order_request.quantity,
            raw={"orderId": 123, "status": "NEW"},
        )

    async def cancel_order(self, symbol: str, order_id: int | str) -> dict[str, Any]:
        return {}

    async def get_order(self, symbol: str, order_id: int | str) -> dict[str, Any]:
        return {"status": "FILLED"}


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
async def test_order_manager_blocks_without_risk_approval() -> None:
    session = _session()
    broker = FakeBroker()
    risk = RiskDecision(symbol="BTCUSDT", approved=False, reason="no", risk_state_json={})
    session.add(risk)
    session.flush()
    manager = OrderManager(broker=broker, session=session, trading_mode="testnet")
    with pytest.raises(RiskRejectedError):
        await manager.submit_order(
            signal=_signal(),
            risk_decision=risk,
            order_request=OrderRequest(
                symbol="BTCUSDT", side="BUY", quantity=Decimal("0.1"), price=Decimal("100")
            ),
        )
    assert broker.calls == 0


@pytest.mark.asyncio
async def test_order_manager_submits_and_updates_execution_report() -> None:
    session = _session()
    broker = FakeBroker()
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
    )
    assert record.status == OrderState.WAITING_USER_STREAM.value
    event = {
        "e": "executionReport",
        "c": record.client_order_id,
        "X": "FILLED",
        "x": "TRADE",
        "i": 123,
        "s": "BTCUSDT",
        "S": "BUY",
        "L": "100",
        "l": "0.1",
        "n": "0.01",
        "N": "USDT",
        "E": 1_700_000_000_000,
    }
    updated = manager.handle_execution_report(event)
    assert updated is not None
    assert updated.status == OrderState.FILLED.value
