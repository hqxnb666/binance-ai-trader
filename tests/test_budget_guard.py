from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ai.budget_guard import BudgetGuard
from ai.model_router import OpenAIModelRole
from config.settings import load_settings
from journal.models import Base
from journal.openai_usage_store import record_openai_usage


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)()


def test_budget_guard_allows_when_under_budget(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_DAILY_BUDGET_USD", "1")
    settings = load_settings()
    decision = BudgetGuard(settings, _session()).check_before_openai_call(
        role=OpenAIModelRole.SIGNAL_REVIEW,
        model="gpt-5.4-mini",
    )
    assert decision.allowed is True
    assert decision.fallback_allowed is False


def test_budget_guard_blocks_daily_budget(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_DAILY_BUDGET_USD", "0.001")
    settings = load_settings()
    session = _session()
    record_openai_usage(
        session,
        role="signal_review",
        model="gpt-5.4-mini",
        operation_name="signal_review",
        status="SUCCESS",
        estimated_cost_usd="0.002",
    )
    decision = BudgetGuard(settings, session).check_before_openai_call(
        role=OpenAIModelRole.SIGNAL_REVIEW,
        model="gpt-5.4-mini",
    )
    assert decision.allowed is False
    assert "OPENAI_DAILY_BUDGET_EXCEEDED" in decision.reason_codes


def test_budget_guard_blocks_monthly_budget(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_MONTHLY_BUDGET_USD", "0.001")
    settings = load_settings()
    session = _session()
    record_openai_usage(
        session,
        role="signal_review",
        model="gpt-5.4-mini",
        operation_name="signal_review",
        status="SUCCESS",
        estimated_cost_usd="0.002",
    )
    decision = BudgetGuard(settings, session).check_before_openai_call(
        role=OpenAIModelRole.SIGNAL_REVIEW,
        model="gpt-5.4-mini",
    )
    assert decision.allowed is False
    assert "OPENAI_MONTHLY_BUDGET_EXCEEDED" in decision.reason_codes


def test_strategy_and_signal_call_limits(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_STRATEGY_DAILY_CALL_LIMIT", "1")
    monkeypatch.setenv("OPENAI_SIGNAL_DAILY_CALL_LIMIT", "1")
    settings = load_settings()
    session = _session()
    record_openai_usage(
        session,
        role="strategy_planner",
        model="gpt-5.5",
        operation_name="strategy_planner.full_replan",
        status="SUCCESS",
    )
    record_openai_usage(
        session,
        role="signal_review",
        model="gpt-5.4-mini",
        operation_name="signal_review",
        status="SUCCESS",
    )
    guard = BudgetGuard(settings, session)
    assert guard.check_before_openai_call(
        role=OpenAIModelRole.STRATEGY_PLANNER, model="gpt-5.5"
    ).allowed is False
    assert guard.check_before_openai_call(
        role=OpenAIModelRole.SIGNAL_REVIEW, model="gpt-5.4-mini"
    ).allowed is False
