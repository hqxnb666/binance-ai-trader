from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ShadowDecisionStatus(StrEnum):
    CREATED = "CREATED"
    TRACKING = "TRACKING"
    CLOSED = "CLOSED"
    EXPIRED = "EXPIRED"
    CANCELED = "CANCELED"
    INVALIDATED = "INVALIDATED"


class ShadowDecisionType(StrEnum):
    WOULD_PLACE_ORDER = "WOULD_PLACE_ORDER"
    RISK_REJECTED = "RISK_REJECTED"
    AI_REJECTED = "AI_REJECTED"
    DATA_QUALITY_BLOCKED = "DATA_QUALITY_BLOCKED"
    STRATEGY_NO_TRADE = "STRATEGY_NO_TRADE"
    BUDGET_BLOCKED = "BUDGET_BLOCKED"


class ShadowExitReason(StrEnum):
    TIME_BASED = "TIME_BASED"
    STOP_LOSS_SIMULATED = "STOP_LOSS_SIMULATED"
    TAKE_PROFIT_SIMULATED = "TAKE_PROFIT_SIMULATED"
    INVALIDATED = "INVALIDATED"
    DATA_QUALITY_DEGRADED = "DATA_QUALITY_DEGRADED"
    MANUAL_CANCEL = "MANUAL_CANCEL"
    UNKNOWN = "UNKNOWN"


class ShadowContextSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_name: str | None = None
    signal_type: str | None = None
    ai_decision: str | None = None
    risk_reason: str | None = None
    data_quality_status: str | None = None
    price_source: str | None = None
    notes: list[str] = Field(default_factory=list)


class ShadowDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["shadow_decision_v1"] = "shadow_decision_v1"
    shadow_id: str
    created_at: datetime
    status: ShadowDecisionStatus
    decision_type: ShadowDecisionType
    symbol: str
    side: str
    strategy_plan_id: str | None
    signal_review_id: str | None
    risk_decision_id: str | None
    data_quality_snapshot_id: str | None
    order_would_be_submitted: bool
    order_type: str | None
    simulated_entry_price: str | None
    simulated_quantity: str | None
    simulated_notional: str | None
    reason: str
    reason_codes: list[str]
    context_summary: ShadowContextSummary
    expires_at: datetime
    dry_run: bool
    order_execution_enabled: bool


class ShadowEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["shadow_evaluation_v1"] = "shadow_evaluation_v1"
    shadow_id: str
    evaluated_at: datetime
    current_price: str
    minutes_since_entry: float
    unrealized_pnl_usdt: str
    unrealized_pnl_pct: float
    mfe_usdt: str
    mae_usdt: str
    status: ShadowDecisionStatus
    exit_reason: ShadowExitReason | None


class ShadowTradeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shadow_id: str
    symbol: str
    side: str
    simulated_pnl_usdt: str
    simulated_pnl_pct: float | None


class ShadowRejectionReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str
    count: int


class ShadowReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["shadow_report_v1"] = "shadow_report_v1"
    created_at: datetime
    window_start: datetime
    window_end: datetime
    total_decisions: int
    would_place_order_count: int
    risk_rejected_count: int
    ai_rejected_count: int
    data_quality_blocked_count: int
    closed_shadow_trades: int
    simulated_win_rate: float | None
    simulated_total_pnl_usdt: str
    simulated_avg_pnl_pct: float | None
    best_shadow_trade: ShadowTradeSummary | None
    worst_shadow_trade: ShadowTradeSummary | None
    top_rejection_reasons: list[ShadowRejectionReason]
    attribution_summary: dict[str, int] = Field(default_factory=dict)
    primary_blocking_layer: str = "NO_SAMPLES"
    human_summary: list[str] = Field(default_factory=list)
    summary: str
