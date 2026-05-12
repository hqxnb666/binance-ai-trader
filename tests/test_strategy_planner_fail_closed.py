from __future__ import annotations

from ai.strategy_planner import StrategyPlanner
from ai.strategy_schemas import RiskMode, StrategyPlanningMode
from config.settings import load_settings


class RaisingClient:
    def parse(self, **kwargs):
        raise RuntimeError("boom")


class InvalidClient:
    def parse(self, **kwargs):
        return {"bad": "shape"}


class InvalidOrderFieldClient:
    def parse(self, **kwargs):
        schema = kwargs["schema"]
        return schema.model_validate(
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
                    {"symbol": "ETHUSDT", "permission": "observe_only", "reason": "watch"},
                ],
                "entry_quality_required": "high",
                "invalidation_conditions": ["watch data quality"],
                "expires_at": "2099-01-01T00:00:00+00:00",
                "confidence": 0.8,
                "requires_human_review": False,
                "reason_codes": ["TREND_OK"],
                "explanation": "use price and quantity",
            }
        )


def test_strategy_planner_openai_exception_fail_closed() -> None:
    planner = StrategyPlanner(load_settings(), client=RaisingClient())
    result = planner.plan(planning_mode=StrategyPlanningMode.FULL_REPLAN, context={})
    assert result.schema_valid is False
    assert result.output.risk_mode == RiskMode.NO_TRADE
    assert result.output.requires_human_review is True
    assert "AI_STRATEGY_PLANNER_FAILED" in result.output.reason_codes


def test_strategy_planner_schema_invalid_fail_closed() -> None:
    planner = StrategyPlanner(load_settings(), client=InvalidClient())
    result = planner.plan(planning_mode=StrategyPlanningMode.REFRESH, context={})
    assert result.schema_valid is False
    assert result.output.plan_action == "NO_TRADE"
    assert result.output.requires_human_review is True


def test_strategy_planner_order_field_output_fail_closed() -> None:
    planner = StrategyPlanner(load_settings(), client=InvalidOrderFieldClient())
    result = planner.plan(planning_mode=StrategyPlanningMode.FULL_REPLAN, context={})
    assert result.schema_valid is False
    assert result.output.risk_mode == RiskMode.NO_TRADE
    assert result.output.requires_human_review is True
    assert "STRATEGY_SCHEMA_INVALID" in result.output.reason_codes
