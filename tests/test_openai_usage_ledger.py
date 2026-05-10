from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from journal.models import Base
from journal.openai_usage_store import (
    get_month_openai_cost,
    get_role_call_count_today,
    get_today_openai_cost,
    record_openai_usage,
)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)()


def test_usage_ledger_records_success_and_cost() -> None:
    session = _session()
    record = record_openai_usage(
        session,
        role="signal_review",
        model="gpt-5.4-mini",
        operation_name="signal_review",
        status="SUCCESS",
        input_tokens=1000,
        output_tokens=1000,
        total_tokens=2000,
        input_payload={"symbol": "BTCUSDT"},
        output_payload={"decision": "HOLD"},
    )
    assert record.id is not None
    assert get_today_openai_cost(session) == Decimal("0.00525000")
    assert get_month_openai_cost(session) == Decimal("0.00525000")
    assert get_role_call_count_today(session, "signal_review") == 1


def test_usage_ledger_records_failure_without_secret_leak() -> None:
    session = _session()
    record = record_openai_usage(
        session,
        role="strategy_planner",
        model="gpt-5.5",
        operation_name="strategy_planner.full_replan",
        status="FAILED",
        error_type="RuntimeError",
        error_message="bad key sk-secret and api_key=abc",
    )
    assert record.status == "FAILED"
    rendered = str(record.error_message_sanitized)
    assert "sk-secret" not in rendered
    assert "api_key=abc" not in rendered
