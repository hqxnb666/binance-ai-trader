from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from journal.models import Base
from shadow.schemas import (
    ShadowContextSummary,
    ShadowDecision,
    ShadowDecisionStatus,
    ShadowDecisionType,
    ShadowEvaluation,
    ShadowExitReason,
)
from shadow.store import (
    add_shadow_evaluation,
    build_shadow_report,
    close_shadow_decision,
    create_shadow_decision,
    get_shadow_decision,
    list_open_shadow_decisions,
    shadow_decision_to_dict,
)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)()


def _decision(shadow_id: str = "shadow-1") -> ShadowDecision:
    now = datetime.now(UTC)
    return ShadowDecision(
        shadow_id=shadow_id,
        created_at=now,
        status=ShadowDecisionStatus.CREATED,
        decision_type=ShadowDecisionType.WOULD_PLACE_ORDER,
        symbol="BTCUSDT",
        side="BUY",
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
        context_summary=ShadowContextSummary(notes=["api_key should redact"]),
        expires_at=now + timedelta(hours=1),
        dry_run=True,
        order_execution_enabled=False,
    )


def test_shadow_store_lifecycle_and_report_no_secret_leak() -> None:
    session = _session()
    record = create_shadow_decision(session, _decision())
    assert get_shadow_decision(session, record.shadow_id) is not None
    assert len(list_open_shadow_decisions(session)) == 1
    evaluation = ShadowEvaluation(
        shadow_id=record.shadow_id,
        evaluated_at=datetime.now(UTC),
        current_price="110",
        minutes_since_entry=5,
        unrealized_pnl_usdt="1",
        unrealized_pnl_pct=10,
        mfe_usdt="1",
        mae_usdt="0",
        status=ShadowDecisionStatus.TRACKING,
        exit_reason=None,
    )
    add_shadow_evaluation(session, evaluation)
    close_shadow_decision(session, record.shadow_id)
    report = build_shadow_report(session)
    assert report.total_decisions == 1
    assert report.simulated_total_pnl_usdt == "1.000000000000"
    rendered = str(shadow_decision_to_dict(record)).upper()
    assert "SECRET" not in rendered
    assert "API_KEY" not in rendered
    assert ShadowExitReason.TIME_BASED.value == "TIME_BASED"
