from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.data_loader import load_klines_from_binance, parse_backtest_window  # noqa: E402
from backtest.engine import BacktestConfig, BacktestEngine  # noqa: E402
from backtest.metrics import calculate_metrics  # noqa: E402
from backtest.report import write_backtest_report  # noqa: E402
from config.settings import get_settings  # noqa: E402


async def run_backtest(args: argparse.Namespace) -> dict[str, object]:
    settings = get_settings()
    start, end = parse_backtest_window(start=args.start, end=args.end, days=args.days)
    entry_df = await load_klines_from_binance(
        rest_base=settings.binance_spot_testnet_rest_base,
        symbol=args.symbol,
        interval="5m",
        start=start,
        end=end,
    )
    trend_df = await load_klines_from_binance(
        rest_base=settings.binance_spot_testnet_rest_base,
        symbol=args.symbol,
        interval="1h",
        start=start,
        end=end,
    )
    if entry_df.empty or trend_df.empty:
        msg = "No backtest data returned from Binance Testnet REST"
        raise RuntimeError(msg)
    engine = BacktestEngine(settings.strategy.ema_trend)
    trades = engine.run(
        entry_df=entry_df,
        trend_df=trend_df,
        config=BacktestConfig(
            symbol=args.symbol,
            initial_equity=args.initial_equity,
            position_pct=args.position_pct,
            fee_pct=args.fee_pct,
            slippage_pct=args.slippage_pct,
        ),
    )
    metrics = calculate_metrics(trades, total_bars=len(entry_df))
    paths = write_backtest_report(
        output_dir=ROOT / "reports" / "backtests",
        symbol=args.symbol,
        trades=trades,
        metrics=metrics,
        metadata={
            "start": start.isoformat(),
            "end": end.isoformat(),
            "fee_pct": args.fee_pct,
            "slippage_pct": args.slippage_pct,
            "data_source": "binance_testnet_rest",
        },
    )
    return {"metrics": metrics.__dict__, "reports": paths}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True, choices=["BTCUSDT", "ETHUSDT"])
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--days", type=int)
    parser.add_argument("--initial-equity", type=float, default=10_000.0)
    parser.add_argument("--position-pct", type=float, default=0.10)
    parser.add_argument("--fee-pct", type=float, default=0.001)
    parser.add_argument("--slippage-pct", type=float, default=0.0002)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = asyncio.run(run_backtest(args))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "FAILED", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps({"status": "OK", **result}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

