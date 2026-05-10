from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from binance_client.exchange_info import SymbolFilters
from config.settings import load_settings
from data_quality.schemas import DataQualitySeverity
from scripts.smoke_test_testnet import _stage2_5_data_quality


def _frame(rows: int) -> pd.DataFrame:
    now = datetime.now(UTC)
    return pd.DataFrame(
        {
            "close_time": [now for _ in range(rows)],
        }
    )


def test_smoke_has_stage_2_5_and_blocks_critical_quality() -> None:
    settings = load_settings()
    report: dict[str, object] = {"stages": []}
    snapshot = {
        "symbol": "BTCUSDT",
        "data_delay_seconds": 1,
        "ema_fast_5m": None,
        "ema_slow_5m": None,
        "ema_fast_1h": None,
        "ema_slow_1h": None,
        "rsi14_5m": None,
        "atr14_5m": None,
        "volume_ratio_5m": None,
    }
    filters = {
        "BTCUSDT": SymbolFilters(
            symbol="BTCUSDT",
            tick_size="0.01",
            step_size="0.000001",
            min_qty="0.000001",
            min_notional="5",
        )
    }
    result = _stage2_5_data_quality(
        report,
        settings,
        {("BTCUSDT", "5m"): _frame(10), ("BTCUSDT", "1h"): _frame(10)},
        filters,
        snapshot,
        require_real_order=False,
    )
    assert report["stages"][0]["name"] == "Stage 2.5: DataQualityGate"
    assert result["overall_status"] == DataQualitySeverity.CRITICAL.value
    assert result["safe_for_signal_review"] is False
