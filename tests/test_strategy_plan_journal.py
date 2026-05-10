from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ai.strategy_schemas import StrategyPlan
from journal.models import Base
from journal.strategy_plan_store import (
    expire_strategy_plan,
    get_active_strategy_plan,
    save_strategy_plan,
)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)()


def _plan() -> StrategyPlan:
    return StrategyPlan.model_validate(
        {
            "schema_version": "strategy_plan_v1",
            "plan_action": "CREATE",
            "planning_mode": "FULL_REPLAN",
            "symbol_scope": ["BTCUSDT"],
            "market_regime": "uncertain",
            "trade_bias": "no_trade",
            "allowed_actions": [],
            "blocked_actions": ["MARTINGALE", "LEVERAGE", "SHORT"],
            "risk_mode": "no_trade",
            "max_position_pct": 0,
            "symbol_permissions": [
                {"symbol": "BTCUSDT", "permission": "blocked", "reason": "fallback"}
            ],
            "entry_quality_required": "very_high",
            "invalidation_conditions": ["fallback"],
            "expires_at": datetime.now(UTC) + timedelta(hours=1),
            "confidence": 0,
            "requires_human_review": True,
            "reason_codes": ["TEST"],
            "explanation": "test",
        }
    )


def test_strategy_plan_save_get_expire_and_sanitize() -> None:
    session = _session()
    record = save_strategy_plan(
        session,
        plan=_plan(),
        raw_input_json={"OPENAI_API_KEY": "sk-secret", "nested": {"secret": "x"}},
        model="gpt-5.5",
    )
    assert record.id is not None
    assert get_active_strategy_plan(session).id == record.id
    assert "sk-secret" not in str(record.raw_input_json)
    expire_strategy_plan(session, record.id)
    assert get_active_strategy_plan(session) is None
