from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ai.signal_reviewer import SignalReviewer
from config.settings import load_settings
from journal.models import Base


class ShouldNotCallClient:
    def parse(self, **kwargs):
        raise AssertionError("OpenAI should not be called when BudgetGuard blocks")


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)()


def test_signal_reviewer_budget_block_does_not_approve(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_DAILY_BUDGET_USD", "0")
    settings = load_settings()
    reviewer = SignalReviewer(settings, client=ShouldNotCallClient())

    result = reviewer.review_with_schema(
        {"symbol": "BTCUSDT", "strategy_signal": {"side": "BUY"}},
        usage_session=_session(),
    )

    assert result.approved_for_risk is False
    assert result.reason == "BUDGET_GUARD_BLOCKED"
    assert result.review.decision == "HUMAN_REVIEW_REQUIRED"
    assert result.review.side == "HOLD"
