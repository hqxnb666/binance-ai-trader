from __future__ import annotations

import pandas as pd

from config.settings import EmaTrendConfig
from features.indicators import calculate_indicators
from strategies.base import Strategy, StrategySignalPayload


class EmaTrendStrategy(Strategy):
    name = "ema_trend"
    version = "v1.0"

    def __init__(self, config: EmaTrendConfig):
        self.config = config

    def generate_signal(
        self,
        *,
        symbol: str,
        entry_df: pd.DataFrame,
        trend_df: pd.DataFrame,
        current_position_pct: float = 0,
        ws_health: str = "ok",
    ) -> StrategySignalPayload | None:
        if not self.config.enabled or ws_health != "ok":
            return None
        entry = calculate_indicators(
            entry_df,
            ema_fast_period=self.config.ema_fast,
            ema_slow_period=self.config.ema_slow,
            rsi_period=self.config.rsi_period,
            atr_period=self.config.atr_period,
        )
        trend = calculate_indicators(
            trend_df,
            ema_fast_period=self.config.ema_fast,
            ema_slow_period=self.config.ema_slow,
            rsi_period=self.config.rsi_period,
            atr_period=self.config.atr_period,
        )
        if not entry.get("tradable") or not trend.get("tradable"):
            return None
        buy_conditions = [
            trend["ema_fast"] > trend["ema_slow"],
            entry["close"] > entry["ema_fast"],
            entry["ema_fast"] > entry["ema_slow"],
            self.config.rsi_min <= entry["rsi"] <= self.config.rsi_max,
            entry["volume_ratio"] >= self.config.volume_ratio_min,
            current_position_pct < 0.01,
        ]
        if all(buy_conditions):
            return StrategySignalPayload(
                symbol=symbol,
                strategy_name=self.name,
                strategy_version=self.version,
                timeframe=self.config.entry_timeframe,
                side="BUY",
                signal_type="ENTRY_CANDIDATE",
                confidence=0.68,
                reason="5m close above EMA20 with 1h trend up",
                raw_payload_json={"entry": entry, "trend": trend, "ws_health": ws_health},
            )
        if entry["close"] < entry["ema_slow"] and current_position_pct > 0:
            return StrategySignalPayload(
                symbol=symbol,
                strategy_name=self.name,
                strategy_version=self.version,
                timeframe=self.config.entry_timeframe,
                side="SELL",
                signal_type="EXIT_CANDIDATE",
                confidence=0.62,
                reason="5m close below EMA60 exit candidate",
                raw_payload_json={"entry": entry, "trend": trend, "ws_health": ws_health},
            )
        return None

