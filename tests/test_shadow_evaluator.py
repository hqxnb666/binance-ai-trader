from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import load_settings
from journal.models import Base
from shadow.evaluator import ShadowModeEvaluator
from shadow.schemas import (
    ShadowContextSummary,
    ShadowDecision,
    ShadowDecisionStatus,
    ShadowDecisionType,
)
from shadow.store import create_shadow_decision, get_shadow_decision, list_recent_shadow_decisions


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)()


def _decision(*, side: str = "BUY", expires_at: datetime | None = None) -> ShadowDecision:
    now = datetime.now(UTC)
    return ShadowDecision(
        shadow_id=f"shadow-{side.lower()}",
        created_at=now - timedelta(minutes=10),
        status=ShadowDecisionStatus.CREATED,
        decision_type=ShadowDecisionType.WOULD_PLACE_ORDER,
        symbol="BTCUSDT",
        side=side,
        strategy_plan_id=None,
        signal_review_id=None,
        risk_decision_id=None,
        data_quality_snapshot_id=None,
        order_would_be_submitted=True,
        order_type="LIMIT",
        simulated_entry_price="100",
        simulated_quantity="0.1",
        simulated_notional="10",
        reason="ok",
        reason_codes=["WOULD_PLACE_ORDER"],
        context_summary=ShadowContextSummary(),
        expires_at=expires_at or (now + timedelta(hours=1)),
        dry_run=True,
        order_execution_enabled=False,
    )


def test_buy_pnl_and_mfe_mae_are_calculated() -> None:
    session = _session()
    create_shadow_decision(session, _decision())
    results = ShadowModeEvaluator(load_settings()).evaluate_open_decisions(
        session,
        current_prices={"BTCUSDT": Decimal("110")},
    )
    assert results[0]["unrealized_pnl_usdt"] == "1.000000000000"
    assert results[0]["mfe_usdt"] == "1.000000000000"
    assert results[0]["mae_usdt"] == "1.000000000000"


def test_expired_shadow_trade_closes_time_based() -> None:
    session = _session()
    decision = create_shadow_decision(
        session,
        _decision(expires_at=datetime.now(UTC) - timedelta(minutes=1)),
    )
    ShadowModeEvaluator(load_settings()).evaluate_open_decisions(
        session,
        current_prices={"BTCUSDT": Decimal("101")},
    )
    assert get_shadow_decision(session, decision.shadow_id).status == "CLOSED"


def test_sell_without_position_is_invalidated_not_shorted() -> None:
    session = _session()
    create_shadow_decision(session, _decision(side="SELL"))
    results = ShadowModeEvaluator(load_settings()).evaluate_open_decisions(
        session,
        current_prices={"BTCUSDT": Decimal("90")},
    )
    assert results[0]["status"] == "INVALIDATED"
    assert list_recent_shadow_decisions(session, limit=1)[0].status == "INVALIDATED"
