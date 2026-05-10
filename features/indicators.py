from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.astype(float).ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    close = close.astype(float)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    values = 100 - (100 / (1 + rs))
    return values.fillna(100)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    prev_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def volume_ratio(df: pd.DataFrame, period: int = 20) -> pd.Series:
    volume = df["volume"].astype(float)
    rolling = volume.rolling(period, min_periods=period).mean()
    return volume / rolling.replace(0, np.nan)


def trend_state(ema_fast: float, ema_slow: float, tolerance_pct: float = 0.001) -> str:
    if ema_slow == 0 or np.isnan(ema_fast) or np.isnan(ema_slow):
        return "unknown"
    diff_pct = (ema_fast - ema_slow) / ema_slow
    if diff_pct > tolerance_pct:
        return "up"
    if diff_pct < -tolerance_pct:
        return "down"
    return "flat"


def calculate_indicators(
    df: pd.DataFrame,
    *,
    ema_fast_period: int = 20,
    ema_slow_period: int = 60,
    rsi_period: int = 14,
    atr_period: int = 14,
    volume_period: int = 20,
) -> dict[str, Any]:
    required = max(ema_slow_period, rsi_period + 1, atr_period + 1, volume_period) + 1
    if len(df) < required:
        return {
            "data_sufficient": False,
            "required_bars": required,
            "available_bars": len(df),
            "tradable": False,
        }
    frame = df.copy()
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = frame[column].astype(float)
    ema_fast_series = ema(frame["close"], ema_fast_period)
    ema_slow_series = ema(frame["close"], ema_slow_period)
    rsi_series = rsi(frame["close"], rsi_period)
    atr_series = atr(frame, atr_period)
    volume_ratio_series = volume_ratio(frame, volume_period)
    latest = {
        "data_sufficient": True,
        "tradable": True,
        "close": float(frame["close"].iloc[-1]),
        "ema_fast": float(ema_fast_series.iloc[-1]),
        "ema_slow": float(ema_slow_series.iloc[-1]),
        "rsi": float(rsi_series.iloc[-1]),
        "atr": float(atr_series.iloc[-1]),
        "volume_ratio": float(volume_ratio_series.iloc[-1]),
    }
    latest["trend"] = trend_state(latest["ema_fast"], latest["ema_slow"])
    if any(np.isnan(float(latest[key])) for key in ["ema_fast", "ema_slow", "rsi", "atr"]):
        latest["tradable"] = False
    return latest

