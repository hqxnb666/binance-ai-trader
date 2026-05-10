from __future__ import annotations

from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from features.indicators import calculate_indicators
from strategies.base import StrategySignalPayload


class MarketSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    entry_timeframe: str
    trend_timeframe: str
    price: float
    ema_fast_5m: float | None = None
    ema_slow_5m: float | None = None
    ema_fast_1h: float | None = None
    ema_slow_1h: float | None = None
    rsi14_5m: float | None = None
    atr14_5m: float | None = None
    volume_ratio_5m: float | None = None
    trend_1h: str
    current_position_pct: float = 0
    daily_pnl_pct: float = 0
    consecutive_losses: int = 0
    ws_health: str = "unknown"
    data_delay_seconds: float = 0
    strategy_signal: dict[str, Any] | None = None
    recent_trades: list[dict[str, Any]] = Field(default_factory=list, max_length=5)
    data_sufficient: bool = False

    def compact_dict(self) -> dict[str, Any]:
        data = self.model_dump(exclude_none=True)
        if len(data.get("recent_trades", [])) > 5:
            data["recent_trades"] = data["recent_trades"][-5:]
        return data


def build_market_snapshot(
    *,
    symbol: str,
    entry_df: pd.DataFrame,
    trend_df: pd.DataFrame,
    entry_timeframe: str = "5m",
    trend_timeframe: str = "1h",
    strategy_signal: StrategySignalPayload | None = None,
    current_position_pct: float = 0,
    daily_pnl_pct: float = 0,
    consecutive_losses: int = 0,
    ws_health: str = "unknown",
    data_delay_seconds: float = 0,
    recent_trades: list[dict[str, Any]] | None = None,
) -> MarketSnapshot:
    entry = calculate_indicators(entry_df)
    trend = calculate_indicators(trend_df)
    signal = None
    if strategy_signal:
        signal = {
            "name": strategy_signal.strategy_name,
            "version": strategy_signal.strategy_version,
            "side": strategy_signal.side,
            "reason": strategy_signal.reason,
        }
    price = float(entry_df["close"].astype(float).iloc[-1]) if not entry_df.empty else 0.0
    return MarketSnapshot(
        symbol=symbol.upper(),
        entry_timeframe=entry_timeframe,
        trend_timeframe=trend_timeframe,
        price=price,
        ema_fast_5m=entry.get("ema_fast"),
        ema_slow_5m=entry.get("ema_slow"),
        ema_fast_1h=trend.get("ema_fast"),
        ema_slow_1h=trend.get("ema_slow"),
        rsi14_5m=entry.get("rsi"),
        atr14_5m=entry.get("atr"),
        volume_ratio_5m=entry.get("volume_ratio"),
        trend_1h=str(trend.get("trend", "unknown")),
        current_position_pct=current_position_pct,
        daily_pnl_pct=daily_pnl_pct,
        consecutive_losses=consecutive_losses,
        ws_health=ws_health,
        data_delay_seconds=data_delay_seconds,
        strategy_signal=signal,
        recent_trades=(recent_trades or [])[-5:],
        data_sufficient=bool(entry.get("data_sufficient") and trend.get("data_sufficient")),
    )

