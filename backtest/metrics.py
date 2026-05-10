from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestMetrics:
    total_trades: int
    win_rate: float
    gross_pnl: float
    net_pnl: float
    max_drawdown: float
    profit_factor: float
    average_win: float
    average_loss: float
    expectancy: float
    exposure_time: float
    fees_paid: float


def calculate_metrics(trades: list[dict[str, object]], *, total_bars: int) -> BacktestMetrics:
    total = len(trades)
    if total == 0:
        return BacktestMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    gross_values = [float(trade["gross_pnl"]) for trade in trades]
    net_values = [float(trade["net_pnl"]) for trade in trades]
    fees = [float(trade["fees"]) for trade in trades]
    wins = [value for value in net_values if value > 0]
    losses = [value for value in net_values if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for pnl in net_values:
        equity += pnl
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
    exposure_bars = sum(int(trade.get("bars_held", 0)) for trade in trades)
    return BacktestMetrics(
        total_trades=total,
        win_rate=len(wins) / total,
        gross_pnl=sum(gross_values),
        net_pnl=sum(net_values),
        max_drawdown=max_drawdown,
        profit_factor=gross_profit / gross_loss if gross_loss > 0 else float("inf"),
        average_win=sum(wins) / len(wins) if wins else 0,
        average_loss=sum(losses) / len(losses) if losses else 0,
        expectancy=sum(net_values) / total,
        exposure_time=exposure_bars / total_bars if total_bars else 0,
        fees_paid=sum(fees),
    )

