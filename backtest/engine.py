from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config.settings import EmaTrendConfig
from features.indicators import calculate_indicators
from strategies.ema_trend import EmaTrendStrategy


@dataclass(frozen=True)
class BacktestConfig:
    symbol: str
    initial_equity: float = 10_000.0
    position_pct: float = 0.10
    fee_pct: float = 0.001
    slippage_pct: float = 0.0002


class BacktestEngine:
    def __init__(self, strategy_config: EmaTrendConfig):
        self.strategy = EmaTrendStrategy(strategy_config)
        self.strategy_config = strategy_config

    def run(
        self,
        *,
        entry_df: pd.DataFrame,
        trend_df: pd.DataFrame,
        config: BacktestConfig,
    ) -> list[dict[str, object]]:
        if len(entry_df) < 80 or len(trend_df) < 80:
            msg = "Not enough data for backtest"
            raise ValueError(msg)
        entry_df = entry_df.sort_values("open_time").reset_index(drop=True)
        trend_df = trend_df.sort_values("open_time").reset_index(drop=True)
        trades: list[dict[str, object]] = []
        position: dict[str, object] | None = None
        for idx in range(len(entry_df)):
            entry_slice = entry_df.iloc[: idx + 1].copy()
            current = entry_df.iloc[idx]
            trend_slice = trend_df[trend_df["close_time"] <= current["close_time"]].copy()
            if len(trend_slice) < 80:
                continue
            indicators = calculate_indicators(entry_slice)
            if not indicators.get("tradable"):
                continue
            if position is not None:
                exit_trade = self._maybe_exit(position, current, indicators, idx, config)
                if exit_trade:
                    trades.append(exit_trade)
                    position = None
                continue
            signal = self.strategy.generate_signal(
                symbol=config.symbol,
                entry_df=entry_slice,
                trend_df=trend_slice,
                current_position_pct=0,
                ws_health="ok",
            )
            if signal and signal.side == "BUY":
                entry_price = float(current["close"]) * (1 + config.slippage_pct)
                atr_value = float(indicators["atr"])
                stop_loss = entry_price - (atr_value * self.strategy_config.stop_loss_atr_multiple)
                take_profit = entry_price + (
                    (entry_price - stop_loss) * self.strategy_config.take_profit_r_multiple
                )
                notional = config.initial_equity * config.position_pct
                quantity = notional / entry_price
                position = {
                    "entry_index": idx,
                    "entry_time": current["close_time"],
                    "entry_price": entry_price,
                    "quantity": quantity,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "entry_fee": notional * config.fee_pct,
                }
        if position is not None:
            last = entry_df.iloc[-1]
            trades.append(self._close_position(position, last, len(entry_df) - 1, "end", config))
        return trades

    def _maybe_exit(
        self,
        position: dict[str, object],
        current: pd.Series,
        indicators: dict[str, object],
        idx: int,
        config: BacktestConfig,
    ) -> dict[str, object] | None:
        low = float(current["low"])
        high = float(current["high"])
        close = float(current["close"])
        if low <= float(position["stop_loss"]):
            return self._close_position(
                position,
                current,
                idx,
                "stop_loss",
                config,
                float(position["stop_loss"]),
            )
        if high >= float(position["take_profit"]):
            return self._close_position(
                position, current, idx, "take_profit", config, float(position["take_profit"])
            )
        if close < float(indicators["ema_slow"]):
            return self._close_position(position, current, idx, "ema_exit", config)
        return None

    def _close_position(
        self,
        position: dict[str, object],
        current: pd.Series,
        idx: int,
        reason: str,
        config: BacktestConfig,
        exit_price_override: float | None = None,
    ) -> dict[str, object]:
        exit_price = exit_price_override or float(current["close"])
        exit_price *= 1 - config.slippage_pct
        quantity = float(position["quantity"])
        entry_price = float(position["entry_price"])
        gross = (exit_price - entry_price) * quantity
        exit_fee = exit_price * quantity * config.fee_pct
        fees = float(position["entry_fee"]) + exit_fee
        return {
            "symbol": config.symbol,
            "entry_time": position["entry_time"],
            "exit_time": current["close_time"],
            "entry_price": entry_price,
            "exit_price": exit_price,
            "quantity": quantity,
            "gross_pnl": gross,
            "fees": fees,
            "net_pnl": gross - fees,
            "reason": reason,
            "bars_held": idx - int(position["entry_index"]) + 1,
        }
