from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ai.strategy_planner import StrategyPlanner
from ai.strategy_schemas import RiskMode, StrategyPlanningMode
from config.settings import load_settings
from journal.models import Base, OpenAIUsageRecord
from journal.openai_usage_store import record_openai_usage


class ShouldNotCallClient:
    def parse(self, **kwargs):
        raise AssertionError("OpenAI should not be called when BudgetGuard blocks")


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)()


def test_strategy_planner_budget_block_no_old_plan_returns_no_trade(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_DAILY_BUDGET_USD", "0")
    settings = load_settings()
    session = _session()
    planner = StrategyPlanner(settings, client=ShouldNotCallClient())

    result = planner.plan(
        planning_mode=StrategyPlanningMode.FULL_REPLAN,
        context={},
        usage_session=session,
    )

    assert result.output.risk_mode == RiskMode.NO_TRADE
    assert "BUDGET_GUARD_BLOCKED" in result.output.reason_codes


def test_strategy_planner_budget_block_with_old_plan_keeps_without_extension(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_DAILY_BUDGET_USD", "0")
    settings = load_settings()
    session = _session()
    planner = StrategyPlanner(settings, client=ShouldNotCallClient())

    result = planner.plan(
        planning_mode=StrategyPlanningMode.REFRESH,
        context={},
        active_plan_id="42",
        usage_session=session,
    )

    assert result.output.plan_action == "KEEP"
    assert result.output.previous_plan_id == "42"
    assert result.output.new_expiration_time is None
    assert "BUDGET_GUARD_BLOCKED" in result.output.reason_codes


def test_strategy_planner_budget_block_records_skipped(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_DAILY_BUDGET_USD", "0.001")
    settings = load_settings()
    session = _session()
    record_openai_usage(
        session,
        role="strategy_planner",
        model="gpt-5.5",
        operation_name="strategy_planner.full_replan",
        status="SUCCESS",
        estimated_cost_usd="0.002",
    )
    planner = StrategyPlanner(settings, client=ShouldNotCallClient())
    planner.plan(
        planning_mode=StrategyPlanningMode.FULL_REPLAN,
        context={},
        usage_session=session,
    )
    assert any(row.status == "SKIPPED_BUDGET" for row in session.query(OpenAIUsageRecord).all())
