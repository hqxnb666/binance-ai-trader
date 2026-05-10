from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class MarketKline(Base):
    __tablename__ = "market_klines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    timeframe: Mapped[str] = mapped_column(String(10), index=True)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    high: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    low: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    close: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    volume: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class StrategySignal(Base):
    __tablename__ = "strategy_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    strategy_name: Mapped[str] = mapped_column(String(100))
    strategy_version: Mapped[str] = mapped_column(String(50))
    timeframe: Mapped[str] = mapped_column(String(10))
    side: Mapped[str] = mapped_column(String(10))
    signal_type: Mapped[str] = mapped_column(String(50))
    confidence: Mapped[float] = mapped_column(Numeric(6, 5))
    reason: Mapped[str] = mapped_column(Text)
    raw_payload_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    analysis_type: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(50))
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    output_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    schema_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    decision: Mapped[str] = mapped_column(String(50), default="SCHEMA_INVALID")
    confidence: Mapped[float | None] = mapped_column(Numeric(6, 5), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RiskDecision(Base):
    __tablename__ = "risk_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    signal_id: Mapped[int | None] = mapped_column(ForeignKey("strategy_signals.id"), nullable=True)
    ai_analysis_id: Mapped[int | None] = mapped_column(ForeignKey("ai_analyses.id"), nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(Text)
    risk_state_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class OrderRecord(Base):
    __tablename__ = "order_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exchange_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    client_order_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    side: Mapped[str] = mapped_column(String(10))
    order_type: Mapped[str] = mapped_column(String(20))
    price: Mapped[Decimal | None] = mapped_column(Numeric(28, 12), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    status: Mapped[str] = mapped_column(String(30), index=True)
    trading_mode: Mapped[str] = mapped_column(String(20))
    strategy_name: Mapped[str] = mapped_column(String(100))
    strategy_version: Mapped[str] = mapped_column(String(50))
    ai_analysis_id: Mapped[int | None] = mapped_column(ForeignKey("ai_analyses.id"), nullable=True)
    risk_decision_id: Mapped[int | None] = mapped_column(
        ForeignKey("risk_decisions.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    executions: Mapped[list[TradeExecution]] = relationship(back_populates="order_record")


class TradeExecution(Base):
    __tablename__ = "trade_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_record_id: Mapped[int] = mapped_column(ForeignKey("order_records.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    side: Mapped[str] = mapped_column(String(10))
    price: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    commission: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=Decimal("0"))
    commission_asset: Mapped[str | None] = mapped_column(String(20), nullable=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    raw_event_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    order_record: Mapped[OrderRecord] = relationship(back_populates="executions")


class TradeReview(Base):
    __tablename__ = "trade_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_record_id: Mapped[int] = mapped_column(ForeignKey("order_records.id"), index=True)
    model: Mapped[str] = mapped_column(String(100))
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    grade: Mapped[str] = mapped_column(String(2))
    mistake_tag: Mapped[str] = mapped_column(String(50))
    improvement_candidate: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    trading_mode: Mapped[str] = mapped_column(String(20))
    total_signals: Mapped[int] = mapped_column(Integer, default=0)
    total_orders: Mapped[int] = mapped_column(Integer, default=0)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Numeric(8, 5), default=0)
    pnl: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=Decimal("0"))
    max_drawdown: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=Decimal("0"))
    fees: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=Decimal("0"))
    ai_summary: Mapped[str] = mapped_column(Text, default="")
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RuntimeState(Base):
    __tablename__ = "runtime_state"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class RuntimeEvent(Base):
    __tablename__ = "runtime_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(50), index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    severity: Mapped[str] = mapped_column(String(20), default="INFO")
    message: Mapped[str] = mapped_column(Text, default="")
    raw_event_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PipelineAudit(Base):
    __tablename__ = "pipeline_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(100), index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stage: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    snapshot_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signal_id: Mapped[int | None] = mapped_column(ForeignKey("strategy_signals.id"), nullable=True)
    ai_analysis_id: Mapped[int | None] = mapped_column(ForeignKey("ai_analyses.id"), nullable=True)
    risk_decision_id: Mapped[int | None] = mapped_column(
        ForeignKey("risk_decisions.id"), nullable=True
    )
    order_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("order_records.id"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_context_json: Mapped[dict[str, Any]] = mapped_column(JSON)


class StrategyPlanRecord(Base):
    __tablename__ = "strategy_plan_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    planning_mode: Mapped[str] = mapped_column(String(50), index=True)
    plan_action: Mapped[str] = mapped_column(String(30), index=True)
    model: Mapped[str] = mapped_column(String(100))
    schema_version: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), index=True)
    market_regime: Mapped[str | None] = mapped_column(String(30), nullable=True)
    trade_bias: Mapped[str | None] = mapped_column(String(30), nullable=True)
    risk_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    max_position_pct: Mapped[float | None] = mapped_column(Numeric(8, 5), nullable=True)
    confidence: Mapped[float] = mapped_column(Numeric(6, 5), default=0)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=True)
    symbol_scope_json: Mapped[list[str]] = mapped_column(JSON)
    allowed_actions_json: Mapped[list[str]] = mapped_column(JSON)
    blocked_actions_json: Mapped[list[str]] = mapped_column(JSON)
    symbol_permissions_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    invalidation_conditions_json: Mapped[list[str]] = mapped_column(JSON)
    reason_codes_json: Mapped[list[str]] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(Text)
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    output_hash: Mapped[str] = mapped_column(String(64), index=True)
    raw_input_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    raw_output_json: Mapped[dict[str, Any]] = mapped_column(JSON)


class OpenAIUsageRecord(Base):
    __tablename__ = "openai_usage_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    role: Mapped[str] = mapped_column(String(50), index=True)
    model: Mapped[str] = mapped_column(String(100), index=True)
    operation_name: Mapped[str] = mapped_column(String(100), index=True)
    request_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cached_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message_sanitized: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class TradingIssueReportRecord(Base):
    __tablename__ = "trading_issue_report_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    report_type: Mapped[str] = mapped_column(String(50), index=True)
    model: Mapped[str] = mapped_column(String(100))
    overall_status: Mapped[str] = mapped_column(String(30), index=True)
    highest_severity: Mapped[str] = mapped_column(String(30), index=True)
    issue_count: Mapped[int] = mapped_column(Integer, default=0)
    time_window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    time_window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    raw_input_json_sanitized: Mapped[dict[str, Any]] = mapped_column(JSON)
    raw_output_json_sanitized: Mapped[dict[str, Any]] = mapped_column(JSON)
    summary: Mapped[str] = mapped_column(Text)
    report_path: Mapped[str | None] = mapped_column(Text, nullable=True)


class ShadowDecisionRecord(Base):
    __tablename__ = "shadow_decision_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shadow_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    status: Mapped[str] = mapped_column(String(30), index=True)
    decision_type: Mapped[str] = mapped_column(String(50), index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    side: Mapped[str] = mapped_column(String(10))
    strategy_plan_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    signal_review_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    risk_decision_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    data_quality_snapshot_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    order_would_be_submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    order_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    simulated_entry_price: Mapped[Decimal | None] = mapped_column(
        Numeric(28, 12), nullable=True
    )
    simulated_quantity: Mapped[Decimal | None] = mapped_column(Numeric(28, 12), nullable=True)
    simulated_notional: Mapped[Decimal | None] = mapped_column(Numeric(28, 12), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    reason_codes_json: Mapped[list[str]] = mapped_column(JSON)
    context_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    order_execution_enabled: Mapped[bool] = mapped_column(Boolean, default=False)


class ShadowEvaluationRecord(Base):
    __tablename__ = "shadow_evaluation_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shadow_id: Mapped[str] = mapped_column(String(100), index=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    current_price: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    minutes_since_entry: Mapped[float] = mapped_column(Numeric(12, 4))
    unrealized_pnl_usdt: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    unrealized_pnl_pct: Mapped[float] = mapped_column(Numeric(12, 6))
    mfe_usdt: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    mae_usdt: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    status: Mapped[str] = mapped_column(String(30), index=True)
    exit_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
