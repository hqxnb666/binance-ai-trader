from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

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
    market_stream: dict[str, Any] = {}
    user_stream: dict[str, Any] = {}
    budget_status: dict[str, Any] = {}
    audit_status: dict[str, Any] = {}
    health_warning: bool = False
