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

