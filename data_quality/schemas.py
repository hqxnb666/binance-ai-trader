from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DataQualitySeverity(StrEnum):
    OK = "OK"
    INFO = "INFO"
    WARNING = "WARNING"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"


class DataQualityCategory(StrEnum):
    MARKET_STREAM = "MARKET_STREAM"
    USER_STREAM = "USER_STREAM"
    KLINE_STALENESS = "KLINE_STALENESS"
    INDICATORS = "INDICATORS"
    EXCHANGE_FILTERS = "EXCHANGE_FILTERS"
    ACCOUNT_STATE = "ACCOUNT_STATE"
    POSITION_STATE = "POSITION_STATE"
    RUNTIME_STATE = "RUNTIME_STATE"
    DIAGNOSTICS = "DIAGNOSTICS"
    STRATEGY_PLAN = "STRATEGY_PLAN"
    OPENAI_USAGE = "OPENAI_USAGE"
    UNKNOWN = "UNKNOWN"


class DataQualityAction(StrEnum):
    ALLOW = "ALLOW"
    WARN = "WARN"
    BLOCK_STRATEGY_PLANNER = "BLOCK_STRATEGY_PLANNER"
    BLOCK_SIGNAL_REVIEW = "BLOCK_SIGNAL_REVIEW"
    BLOCK_ORDER = "BLOCK_ORDER"
    BLOCK_RUNTIME_START = "BLOCK_RUNTIME_START"


class DataQualityIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: DataQualitySeverity
    category: DataQualityCategory
    title: str
    evidence: list[str] = Field(default_factory=list)
    recommended_action: str
    blocks_strategy_planner: bool
    blocks_signal_review: bool
    blocks_order: bool
    requires_human_review: bool


class DataQualitySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["data_quality_snapshot_v1"] = "data_quality_snapshot_v1"
    created_at: datetime
    overall_status: DataQualitySeverity
    action: DataQualityAction
    issues: list[DataQualityIssue]
    market_stream_connected: bool | None
    user_stream_connected: bool | None
    last_kline_time: datetime | None
    last_user_event_time: datetime | None
    data_delay_seconds: float | None
    kline_staleness_seconds: float | None
    indicator_nan_count: int
    exchange_filters_available: bool | None
    account_state_status: Literal["ok", "unknown", "simulated_default", "error"]
    position_state_status: Literal["ok", "unknown", "simulated_default", "error"]
    safe_for_strategy_planner: bool
    safe_for_signal_review: bool
    safe_for_order: bool
    safe_for_real_testnet_order: bool
    reason_codes: list[str]
