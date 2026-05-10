from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from runtime.daemon_state import DaemonState


class RuntimeHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: DaemonState
    trading_mode: str
    symbols: list[str]
    market_stream_connected: bool
    user_stream_connected: bool
    last_kline_time: str | None
    last_user_event_time: str | None
    last_error: str | None
    dry_run: bool
    ai_enabled: bool
    order_execution_enabled: bool
    reconnecting: bool = False
    data_delay_seconds: float | None = None
    market_stream: dict[str, Any] = Field(default_factory=dict)
    user_stream: dict[str, Any] = Field(default_factory=dict)
    budget_status: dict[str, Any] = Field(default_factory=dict)
    audit_status: dict[str, Any] = Field(default_factory=dict)
    data_quality_status: dict[str, Any] = Field(default_factory=dict)
    account_position_status: dict[str, Any] = Field(default_factory=dict)
    risk_runtime_status: dict[str, Any] = Field(default_factory=dict)
    kill_switch_state: dict[str, Any] = Field(default_factory=dict)
    shadow_status: dict[str, Any] = Field(default_factory=dict)
    health_warning: bool = False
