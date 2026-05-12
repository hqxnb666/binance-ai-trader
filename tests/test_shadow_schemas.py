from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from shadow.schemas import (
    ShadowContextSummary,
    ShadowDecision,
    ShadowDecisionStatus,
    ShadowDecisionType,
    ShadowEvaluation,
    ShadowExitReason,
    ShadowReport,
)


def test_shadow_decision_valid_sample() -> None:
    now = datetime.now(UTC)
    decision = ShadowDecision(
        shadow_id="shadow-test",
        created_at=now,
        status=ShadowDecisionStatus.CREATED,
        decision_type=ShadowDecisionType.WOULD_PLACE_ORDER,
        symbol="BTCUSDT",
        side="BUY",
        strategy_plan_id=None,
        signal_review_id="1",
        risk_decision_id="2",
        data_quality_snapshot_id=None,
        order_would_be_submitted=True,
        order_type="LIMIT",
        simulated_entry_price="100",
        simulated_quantity="0.1",
        simulated_notional="10",
        reason="dry run order",
        reason_codes=["WOULD_PLACE_ORDER"],
        context_summary=ShadowContextSummary(strategy_name="ema_trend"),
        expires_at=now + timedelta(hours=1),
        dry_run=True,
        order_execution_enabled=False,
    )
    assert decision.model_dump(mode="json")["symbol"] == "BTCUSDT"


def test_shadow_evaluation_valid_sample() -> None:
    evaluation = ShadowEvaluation(
        shadow_id="shadow-test",
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
    assert evaluation.current_price == "110"


def test_shadow_report_valid_sample_and_extra_forbidden() -> None:
    now = datetime.now(UTC)
    report = ShadowReport(
        created_at=now,
        window_start=now - timedelta(hours=24),
        window_end=now,
        total_decisions=1,
        would_place_order_count=1,
        risk_rejected_count=0,
        ai_rejected_count=0,
        data_quality_blocked_count=0,
        closed_shadow_trades=0,
        simulated_win_rate=None,
        simulated_total_pnl_usdt="0",
        simulated_avg_pnl_pct=None,
        best_shadow_trade=None,
        worst_shadow_trade=None,
        top_rejection_reasons=[],
        summary="ok",
    )
    assert report.schema_version == "shadow_report_v1"
    assert report.primary_blocking_layer == "NO_SAMPLES"
    with pytest.raises(ValidationError):
        ShadowContextSummary(strategy_name="x", unexpected=True)


def test_shadow_exit_reason_values() -> None:
    assert ShadowExitReason.TIME_BASED.value == "TIME_BASED"
