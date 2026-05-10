from __future__ import annotations

import numpy as np
import pandas as pd

from features.indicators import atr, calculate_indicators, ema, rsi


def _frame(rows: int = 100) -> pd.DataFrame:
    close = np.linspace(100, 130, rows)
    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": np.linspace(1000, 1500, rows),
        }
    )


def test_ema_rsi_atr_calculate() -> None:
    frame = _frame()
    assert ema(frame["close"], 20).iloc[-1] > 0
    assert 0 <= rsi(frame["close"], 14).iloc[-1] <= 100
    assert atr(frame, 14).iloc[-1] > 0
    result = calculate_indicators(frame)
    assert result["data_sufficient"] is True
    assert result["tradable"] is True
    assert result["trend"] == "up"


def test_data_insufficient_returns_not_tradable() -> None:
    result = calculate_indicators(_frame(10))
    assert result["data_sufficient"] is False
    assert result["tradable"] is False

