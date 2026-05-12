from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ai.strategy_schemas import StrategyPlan, StrategyPlanUpdate


def _valid_plan(**overrides):
    payload = {
        "schema_version": "strategy_plan_v1",
        "plan_action": "CREATE",
        "planning_mode": "FULL_REPLAN",
        "symbol_scope": ["BTCUSDT", "ETHUSDT"],
        "market_regime": "trend_up",
        "trade_bias": "long_only",
        "allowed_actions": ["HOLD", "BUY"],
        "blocked_actions": ["MARTINGALE", "LEVERAGE", "SHORT"],
        "risk_mode": "conservative",
        "max_position_pct": 3,
        "symbol_permissions": [
            {"symbol": "BTCUSDT", "permission": "allow", "reason": None},
            {"symbol": "ETHUSDT", "permission": "observe_only", "reason": "watch only"},
        ],
        "entry_quality_required": "high",
        "invalidation_conditions": ["data quality poor"],
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
        "confidence": 0.8,
        "requires_human_review": False,
        "reason_codes": ["TREND_OK"],
        "explanation": "Trend is acceptable for observation.",
    }
    payload.update(overrides)
    return StrategyPlan.model_validate(payload)


def test_strategy_plan_valid_sample_passes() -> None:
    plan = _valid_plan()
    assert plan.plan_action == "CREATE"
    assert plan.symbol_permissions[0].symbol == "BTCUSDT"


def test_strategy_plan_update_keep_passes() -> None:
    update = StrategyPlanUpdate.model_validate(
        {
            "schema_version": "strategy_plan_update_v1",
            "plan_action": "KEEP",
            "planning_mode": "REFRESH",
            "previous_plan_id": "1",
            "is_previous_plan_still_valid": True,
            "changes": [],
            "new_expiration_time": datetime.now(UTC) + timedelta(hours=1),
            "confidence": 0.8,
            "requires_human_review": False,
            "reason_codes": ["NO_MAJOR_CHANGE"],
            "explanation": "Keep the existing plan.",
        }
    )
    assert update.plan_action == "KEEP"


def test_low_confidence_requires_human_review() -> None:
    with pytest.raises(ValueError):
        _valid_plan(confidence=0.5, requires_human_review=False)


def test_no_trade_cannot_allow_buy() -> None:
    with pytest.raises(ValueError):
        _valid_plan(risk_mode="no_trade", allowed_actions=["BUY"])


def test_blocked_actions_are_required() -> None:
    with pytest.raises(ValueError):
        _valid_plan(blocked_actions=["MARTINGALE"])


def test_order_fields_are_forbidden() -> None:
    with pytest.raises(ValueError):
        _valid_plan(explanation="please place_order with quantity and price")


def test_extra_order_field_is_forbidden() -> None:
    with pytest.raises(ValueError):
        _valid_plan(order_type="LIMIT")


def test_safe_normalization_does_not_expand_permissions() -> None:
    plan = _valid_plan(
        allowed_actions=["hold_only"],
        symbol_permissions=[
            {"symbol": "BTCUSDT", "permission": "observe", "reason": "watch"},
            {"symbol": "ETHUSDT", "permission": "observe_only", "reason": "watch"},
        ],
    )
    assert plan.allowed_actions == ["HOLD"]
    assert plan.symbol_permissions[0].permission == "observe_only"
