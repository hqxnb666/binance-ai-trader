from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from broker.base import Broker, OrderRequest, OrderResult
from journal.models import Base, OrderRecord, PipelineAudit
from orders.order_state import OrderState
from orders.reconciliation import reconcile_open_orders


class FillBroker(Broker):
    async def get_account(self) -> dict[str, Any]:
        return {}

    async def get_exchange_info(self) -> dict[str, Any]:
        return {}

    async def get_klines(self, symbol: str, interval: str, limit: int) -> list[list[Any]]:
        return []

    async def place_order(self, order_request: OrderRequest) -> OrderResult:
        raise AssertionError("reconciliation must not place orders")

    async def cancel_order(self, symbol: str, order_id: int | str) -> dict[str, Any]:
        return {}

    async def get_order(self, symbol: str, order_id: int | str) -> dict[str, Any]:
        return {"status": "FILLED"}


@pytest.mark.asyncio
async def test_reconciliation_updates_waiting_order_to_filled() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)()
    order = OrderRecord(
        exchange_order_id="1",
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
    updated = await reconcile_open_orders(broker=FillBroker(), session=session)
    assert updated == 1
    assert order.status == OrderState.FILLED.value
    audits = session.scalars(select(PipelineAudit)).all()
    assert audits[0].stage == "RECONCILED"

