from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backtest.metrics import BacktestMetrics


def write_backtest_report(
    *,
    output_dir: Path,
    symbol: str,
    trades: list[dict[str, object]],
    metrics: BacktestMetrics,
    metadata: dict[str, Any],
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    base = f"backtest-{symbol}-{stamp}"
    json_path = output_dir / f"{base}.json"
    csv_path = output_dir / f"{base}.csv"
    payload = {
        "symbol": symbol,
        "created_at": datetime.now(UTC).isoformat(),
        "metadata": metadata,
        "metrics": asdict(metrics),
        "trades": [_json_safe_trade(trade) for trade in trades],
        "disclaimer": "Backtests do not guarantee future returns.",
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = list(payload["trades"][0].keys()) if payload["trades"] else ["symbol"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(payload["trades"])
    return {"json": str(json_path), "csv": str(csv_path)}


def _json_safe_trade(trade: dict[str, object]) -> dict[str, object]:
    safe: dict[str, object] = {}
    for key, value in trade.items():
        if hasattr(value, "isoformat"):
            safe[key] = value.isoformat()
        else:
            safe[key] = value
    return safe

