from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import load_settings
from journal.models import Base
from shadow.attribution import (
    ShadowAttributionRecorder,
    build_shadow_attribution_summary,
    list_recent_shadow_attributions,
    primary_blocking_layer,
    shadow_attribution_to_dict,
)
from shadow.store import build_shadow_report


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)()


def _recorder() -> ShadowAttributionRecorder:
    return ShadowAttributionRecorder(load_settings())


def test_shadow_attribution_records_local_no_signal() -> None:
    session = _session()
    _recorder().record(
        session,
        symbol="BTCUSDT",
        local_strategy={"has_candidate": False, "reason": "no signal"},
        data_quality_gate={
            "status": "OK",
            "safe_for_signal_review": True,
            "safe_for_order": True,
            "blocking_reasons": [],
        },
        final_real_order_path={
            "would_submit_real_order": False,
            "blocked_by": "LOCAL_STRATEGY_NO_SIGNAL",
        },
        shadow_observation={
            "candidate_observed": False,
            "stage_reached": "LOCAL_SIGNAL",
            "primary_blocker": "LOCAL_STRATEGY",
            "notes": ["LOCAL_STRATEGY_NO_SIGNAL"],
        },
    )
    summary = build_shadow_attribution_summary(session)
    assert summary["local_no_signal_count"] == 1
    assert primary_blocking_layer(summary) == "LOCAL_STRATEGY"


def test_shadow_attribution_records_strategy_plan_block_without_ordering() -> None:
    session = _session()
    _recorder().record(
        session,
        symbol="BTCUSDT",
        side="BUY",
        local_strategy={"has_candidate": True, "confidence": 0.68, "reason": "candidate"},
        data_quality_gate={
            "status": "OK",
            "safe_for_signal_review": True,
            "safe_for_order": True,
            "blocking_reasons": [],
        },
        strategy_plan_gate={
            "active_plan_id": 7,
            "risk_mode": "no_trade",
            "trade_bias": "no_trade",
            "requires_human_review": True,
            "allowed_actions": ["HOLD"],
            "symbol_permission": "observe_only",
            "blocks_real_order": True,
            "blocks_shadow_evaluation": False,
        },
        ai_review={"decision": "HUMAN_REVIEW_REQUIRED", "requires_human_review": True},
        risk_engine={"approved": None, "evaluated_with_account_profile": "dry_run_flat_profile"},
        final_real_order_path={
            "would_submit_real_order": False,
            "blocked_by": "STRATEGY_PLAN_BLOCKED_REAL_ORDER",
        },
        shadow_observation={
            "candidate_observed": True,
            "stage_reached": "AI_REVIEW",
            "primary_blocker": "STRATEGY_PLAN",
            "notes": ["STRATEGY_PLAN_BLOCKED_REAL_ORDER"],
        },
    )
    rows = list_recent_shadow_attributions(session)
    payload = shadow_attribution_to_dict(rows[0])
    assert payload["local_strategy"]["has_candidate"] is True
    assert payload["strategy_plan_gate"]["blocks_real_order"] is True
    summary = build_shadow_attribution_summary(session)
    assert summary["local_candidate_count"] == 1
    assert summary["strategy_plan_blocked_real_order_count"] == 1
    assert summary["strategy_plan_no_trade_count"] == 1
    assert primary_blocking_layer(summary) == "STRATEGY_PLAN"


def test_shadow_attribution_records_shadow_would_place_order_without_broker() -> None:
    session = _session()
    _recorder().record(
        session,
        symbol="ETHUSDT",
        side="BUY",
        local_strategy={"has_candidate": True, "confidence": 0.68, "reason": "candidate"},
        data_quality_gate={
            "status": "OK",
            "safe_for_signal_review": True,
            "safe_for_order": True,
            "blocking_reasons": [],
        },
        strategy_plan_gate={
            "risk_mode": "normal",
            "trade_bias": "long_only",
            "requires_human_review": False,
            "allowed_actions": ["BUY"],
            "symbol_permission": "allow",
            "blocks_real_order": False,
            "blocks_shadow_evaluation": False,
        },
        ai_review={
            "decision": "APPROVE_TO_RISK_ENGINE",
            "requires_human_review": False,
            "schema_valid": True,
        },
        risk_engine={"approved": True, "reason": "approved"},
        final_real_order_path={
            "would_submit_real_order": False,
            "blocked_by": "WOULD_PLACE_ORDER_SHADOW_ONLY",
        },
        shadow_observation={
            "candidate_observed": True,
            "stage_reached": "WOULD_PLACE_ORDER",
            "primary_blocker": "NONE",
            "notes": ["WOULD_PLACE_ORDER_SHADOW_ONLY"],
        },
    )
    summary = build_shadow_attribution_summary(session)
    assert summary["ai_approved_count"] == 1
    assert summary["risk_approved_count"] == 1
    assert summary["would_place_order_shadow_count"] == 1
    assert primary_blocking_layer(summary) == "NONE"
    report = build_shadow_report(session)
    assert report.attribution_summary["would_place_order_shadow_count"] == 1
    assert report.primary_blocking_layer == "NONE"
