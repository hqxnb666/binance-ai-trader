from __future__ import annotations

from ai.schemas import SignalReview
from ai.signal_reviewer import SignalReviewer
from config.settings import load_settings


class CapturingClient:
    def __init__(self):
        self.payload = None
        self.model_override = None

    def parse(self, **kwargs):
        self.payload = kwargs["user_payload"]
        self.model_override = kwargs["model_override"]
        return SignalReview.model_validate(
            {
                "decision": "HUMAN_REVIEW_REQUIRED",
                "symbol": "BTCUSDT",
                "side": "HOLD",
                "confidence": 0.7,
                "risk_level": "medium",
                "market_regime": "unclear",
                "reason": "context captured",
                "warnings": [],
                "max_position_pct": 0,
                "requires_human_review": True,
            }
        )


def test_signal_reviewer_payload_contains_active_strategy_plan() -> None:
    client = CapturingClient()
    reviewer = SignalReviewer(load_settings(), client=client)
    reviewer.review_with_schema(
        {"symbol": "BTCUSDT", "strategy_signal": {"side": "BUY"}},
        active_strategy_plan={"id": 10, "risk_mode": "conservative"},
    )
    assert client.payload["signal_review_context"]["active_strategy_plan"]["id"] == 10
    assert client.model_override == "gpt-5.4-mini"


def test_no_trade_plan_blocks_buy_without_approval() -> None:
    reviewer = SignalReviewer(load_settings(), client=CapturingClient())
    result = reviewer.review_with_schema(
        {"symbol": "BTCUSDT", "strategy_signal": {"side": "BUY"}},
        active_strategy_plan={"id": 1, "risk_mode": "no_trade"},
    )
    assert result.approved_for_risk is False
    assert result.review.decision == "HUMAN_REVIEW_REQUIRED"

