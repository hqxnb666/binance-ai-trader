from __future__ import annotations

import numpy as np
import pandas as pd

from features.market_snapshot import build_market_snapshot


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


def test_market_snapshot_is_compact_and_limits_recent_trades() -> None:
    snapshot = build_market_snapshot(
        symbol="btcusdt",
        entry_df=_frame(),
        trend_df=_frame(),
        recent_trades=[{"id": i} for i in range(10)],
        ws_health="ok",
    )
    data = snapshot.compact_dict()
    assert data["symbol"] == "BTCUSDT"
    assert data["data_sufficient"] is True
    assert len(data["recent_trades"]) == 5

