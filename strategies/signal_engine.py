from __future__ import annotations

import pandas as pd

from strategies.base import StrategySignalPayload
from strategies.ema_trend import EmaTrendStrategy


class SignalEngine:
    def __init__(self, strategies: list[EmaTrendStrategy]):
        self.strategies = strategies

    def generate(
        self,
        *,
        symbol: str,
        entry_df: pd.DataFrame,
        trend_df: pd.DataFrame,
        current_position_pct: float = 0,
        ws_health: str = "ok",
    ) -> list[StrategySignalPayload]:
        signals: list[StrategySignalPayload] = []
        for strategy in self.strategies:
            signal = strategy.generate_signal(
                symbol=symbol,
                entry_df=entry_df,
                trend_df=trend_df,
                current_position_pct=current_position_pct,
                ws_health=ws_health,
            )
            if signal:
                signals.append(signal)
        return signals

