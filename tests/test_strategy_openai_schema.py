from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from ai.strategy_schemas import StrategyPlan, StrategyPlanUpdate


def test_strategy_plan_schema_required_matches_properties() -> None:
    schema = StrategyPlan.model_json_schema()
    properties = schema["properties"]
    required = set(schema["required"])

    assert "symbol_permissions" in properties
    assert "symbol_permissions" in required
    assert required <= set(properties)


def test_strategy_plan_update_schema_required_matches_properties() -> None:
    schema = StrategyPlanUpdate.model_json_schema()
    assert set(schema["required"]) <= set(schema["properties"])


def test_strategy_schemas_are_openai_strict_compatible() -> None:
    for schema in (StrategyPlan.model_json_schema(), StrategyPlanUpdate.model_json_schema()):
        _assert_object_schemas_are_strict(schema)


def test_symbol_permissions_is_array_of_rules_not_free_dict() -> None:
    schema = StrategyPlan.model_json_schema()
    symbol_permissions = schema["properties"]["symbol_permissions"]

    assert symbol_permissions["type"] == "array"
    assert "items" in symbol_permissions
    assert "additionalProperties" not in symbol_permissions

    rule_schema = schema["$defs"]["SymbolPermissionRule"]
    assert rule_schema["additionalProperties"] is False
    assert set(rule_schema["required"]) == {"symbol", "permission", "reason"}


def test_strategy_plan_legal_sample_validates() -> None:
    plan = StrategyPlan.model_validate(
        {
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
                {"symbol": "ETHUSDT", "permission": "observe_only", "reason": "weak trend"},
            ],
            "entry_quality_required": "high",
            "invalidation_conditions": ["data quality poor"],
            "expires_at": datetime.now(UTC) + timedelta(hours=1),
            "confidence": 0.8,
            "requires_human_review": False,
            "reason_codes": ["TREND_OK"],
            "explanation": "Trend is acceptable for observation.",
        }
    )
    assert plan.symbol_permissions[0].permission == "allow"


def test_strategy_plan_update_keep_sample_validates() -> None:
    update = StrategyPlanUpdate.model_validate(
        {
            "schema_version": "strategy_plan_update_v1",
            "plan_action": "KEEP",
            "planning_mode": "REFRESH",
            "previous_plan_id": "1",
            "is_previous_plan_still_valid": True,
            "changes": [],
            "new_expiration_time": None,
            "confidence": 0.8,
            "requires_human_review": False,
            "reason_codes": ["NO_MAJOR_CHANGE"],
            "explanation": "Keep the existing plan.",
        }
    )
    assert update.plan_action == "KEEP"


def _assert_object_schemas_are_strict(node: Any) -> None:
    if isinstance(node, dict):
        if node.get("type") == "object" or "properties" in node:
            properties = node.get("properties")
            assert isinstance(properties, dict)
            required = set(node.get("required", []))
            assert required <= set(properties)
            assert node.get("additionalProperties") is not True
        for value in node.values():
            _assert_object_schemas_are_strict(value)
    elif isinstance(node, list):
        for item in node:
            _assert_object_schemas_are_strict(item)
