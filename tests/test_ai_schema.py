from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai.schemas import SignalReview, signal_review_trade_gate


def _review(**overrides: object) -> SignalReview:
    payload = {
        "decision": "APPROVE_TO_RISK_ENGINE",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "confidence": 0.8,
        "risk_level": "low",
        "market_regime": "trend_up",
        "reason": "Trend aligned.",
        "warnings": [],
        "max_position_pct": 5,
        "requires_human_review": False,
    }
    payload.update(overrides)
    return SignalReview.model_validate(payload)


def test_valid_ai_json_passes() -> None:
    review = _review()
    approved, reason = signal_review_trade_gate(review)
    assert approved is True
    assert reason == "AI approved for risk engine"


def test_invalid_decision_rejected_by_schema() -> None:
    with pytest.raises(ValidationError):
        _review(decision="PLACE_ORDER")


def test_low_confidence_rejected_by_gate() -> None:
    approved, reason = signal_review_trade_gate(_review(confidence=0.2))
    assert approved is False
    assert "confidence" in reason


def test_high_risk_rejected_by_gate() -> None:
    approved, reason = signal_review_trade_gate(_review(risk_level="high"))
    assert approved is False
    assert "high" in reason

