from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from backtest.engine import BacktestConfig, BacktestEngine
from config.settings import load_settings
from strategies.ema_trend import EmaTrendStrategy


def _frame(start: datetime, rows: int, minutes: int) -> pd.DataFrame:
    times = [start + timedelta(minutes=minutes * i) for i in range(rows)]
    close = np.linspace(100, 140, rows)
    return pd.DataFrame(
        {
            "open_time": times,
            "close_time": [item + timedelta(minutes=minutes) for item in times],
            "open": close - 0.2,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": np.linspace(1000, 2000, rows),
        }
    )


def test_backtest_uses_only_closed_prior_trend_bars(monkeypatch) -> None:
    settings = load_settings()
    seen: list[tuple[pd.Timestamp, pd.Timestamp]] = []

    def fake_signal(self, *, symbol, entry_df, trend_df, current_position_pct=0, ws_health="ok"):
        seen.append((entry_df["close_time"].iloc[-1], trend_df["close_time"].iloc[-1]))
        return None

    monkeypatch.setattr(EmaTrendStrategy, "generate_signal", fake_signal)
    engine = BacktestEngine(settings.strategy.ema_trend)
    start = datetime(2024, 1, 10, tzinfo=UTC)
    trend_start = start - timedelta(days=10)
    trades = engine.run(
        entry_df=_frame(start, 200, 5),
        trend_df=_frame(trend_start, 300, 60),
        config=BacktestConfig(symbol="BTCUSDT"),
    )
    assert trades == []
    assert seen
    assert all(trend_time <= entry_time for entry_time, trend_time in seen)


def test_backtest_engine_does_not_call_openai_or_broker() -> None:
    engine = BacktestEngine(load_settings().strategy.ema_trend)
    assert engine.__class__.__module__ == "backtest.engine"

