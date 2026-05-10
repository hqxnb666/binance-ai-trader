from __future__ import annotations

from backtest.metrics import calculate_metrics


def test_backtest_metrics_calculate_expected_values() -> None:
    metrics = calculate_metrics(
        [
            {"gross_pnl": 12, "net_pnl": 10, "fees": 2, "bars_held": 3},
            {"gross_pnl": -5, "net_pnl": -6, "fees": 1, "bars_held": 2},
        ],
        total_bars=10,
    )
    assert metrics.total_trades == 2
    assert metrics.win_rate == 0.5
    assert metrics.gross_pnl == 7
    assert metrics.net_pnl == 4
    assert metrics.fees_paid == 3
    assert metrics.expectancy == 2
    assert metrics.exposure_time == 0.5

