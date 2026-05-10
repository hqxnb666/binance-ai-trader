from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import get_settings  # noqa: E402
from data_quality.gate import DataQualityGate  # noqa: E402
from data_quality.report_store import save_data_quality_report  # noqa: E402


def run_check() -> dict[str, Any]:
    settings = get_settings()
    snapshot = DataQualityGate(settings).evaluate_runtime_health(
        runtime_health={
            "state": "unknown",
            "market_stream_connected": None,
            "user_stream_connected": None,
            "last_kline_time": None,
            "last_user_event_time": None,
            "data_delay_seconds": None,
        },
        exchange_filters_available=None,
        account_state_status="unknown",
        position_state_status="unknown",
        for_real_order=settings.order_execution_enabled and not settings.trading_dry_run,
    )
    return snapshot.model_dump(mode="json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--save-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    snapshot = DataQualityGate(settings).evaluate_runtime_health(
        runtime_health={
            "state": "manual_check",
            "market_stream_connected": None,
            "user_stream_connected": None,
            "last_kline_time": None,
            "last_user_event_time": None,
            "data_delay_seconds": None,
        },
        exchange_filters_available=None,
        account_state_status="unknown",
        position_state_status="unknown",
        for_real_order=settings.order_execution_enabled and not settings.trading_dry_run,
    )
    payload = snapshot.model_dump(mode="json")
    if args.save_report:
        path = save_data_quality_report(snapshot, settings)
        payload["report_path"] = str(path)
    if args.json or args.save_report:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"DataQuality overall_status={snapshot.overall_status} action={snapshot.action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
