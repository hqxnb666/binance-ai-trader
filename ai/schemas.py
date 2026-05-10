from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SignalDecision(StrEnum):
    APPROVE_TO_RISK_ENGINE = "APPROVE_TO_RISK_ENGINE"
    REJECT_SIGNAL = "REJECT_SIGNAL"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


class SignalSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MarketRegime(StrEnum):
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    RANGE = "range"
    HIGH_VOLATILITY = "high_volatility"
    UNCLEAR = "unclear"


class SignalReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: SignalDecision
    symbol: str
    side: SignalSide
    confidence: float = Field(ge=0, le=1)
    risk_level: RiskLevel
    market_regime: MarketRegime
    reason: str = Field(min_length=1, max_length=500)
    warnings: list[str] = Field(default_factory=list)
    max_position_pct: float = Field(ge=0, le=100)
    requires_human_review: bool


class TradeReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grade: Literal["A", "B", "C", "D", "F"]
    entry_quality: Literal["good", "average", "bad"]
    exit_quality: Literal["good", "average", "bad", "not_applicable"]
    mistake_tag: Literal[
        "none",
        "late_entry",
        "early_entry",
        "exit_late",
        "overtrading",
        "bad_market_regime",
        "risk_too_high",
    ]
    main_reason: str
    improvement_candidate: str
    requires_backtest: bool


def signal_review_trade_gate(review: SignalReview) -> tuple[bool, str]:
    if review.decision == SignalDecision.REJECT_SIGNAL:
        return False, "AI rejected signal"
    if review.decision == SignalDecision.HUMAN_REVIEW_REQUIRED or review.requires_human_review:
        return False, "AI requires human review"
    if review.confidence < 0.55:
        return False, "AI confidence below 0.55"
    if review.risk_level == RiskLevel.HIGH:
        return False, "AI risk level is high"
    return True, "AI approved for risk engine"

