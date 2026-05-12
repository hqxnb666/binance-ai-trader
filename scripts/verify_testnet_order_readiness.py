from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from account.state_service import AccountPositionService  # noqa: E402
from broker.binance_spot_testnet import BinanceSpotTestnetBroker  # noqa: E402
from config.settings import Settings, get_settings  # noqa: E402
from data_quality.gate import DataQualityGate  # noqa: E402
from journal.database import SessionLocal, init_db  # noqa: E402
from journal.strategy_plan_store import get_active_strategy_plan  # noqa: E402
from risk.circuit_breaker import CircuitBreaker  # noqa: E402
from scripts.diagnose_binance_signed_requests import run_signed_diagnostics  # noqa: E402

REPORT_DIR = ROOT / "reports" / "readiness"


async def build_readiness_report(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    report: dict[str, Any] = {
        "report_type": "testnet_order_readiness",
        "created_at": datetime.now(UTC).isoformat(),
        "trading_mode": settings.trading_mode,
        "live_disabled": not (settings.live_trading_enabled or settings.live_trading.enabled),
        "dry_run": settings.trading_dry_run,
        "order_execution_enabled": settings.order_execution_enabled,
        "testnet_keys_present": bool(
            settings.binance_testnet_api_key and settings.binance_testnet_api_secret
        ),
        "testnet_rest_ok": False,
        "testnet_user_stream_possible": False,
        "exchange_filters_ok": False,
        "signed_account_ok": False,
        "signed_test_order_ok": False,
        "signed_request_error_code": None,
        "signed_request_error_message_sanitized": None,
        "account_state_status": "UNKNOWN",
        "position_state_status": "UNKNOWN",
        "data_quality_status": "UNKNOWN",
        "kill_switch_enabled": False,
        "strategy_plan_status": "UNKNOWN",
        "budget_status": "UNKNOWN",
        "ready_for_dry_run": False,
        "ready_for_test_order_only": False,
        "ready_for_real_testnet_order": False,
        "ready_for_live": False,
        "blockers": [],
        "warnings": [],
    }
    init_db()
    broker = BinanceSpotTestnetBroker(settings)
    try:
        filters_ok, latest_prices = await _check_rest_and_filters(broker, settings, report)
        report["testnet_rest_ok"] = filters_ok["rest_ok"]
        report["exchange_filters_ok"] = filters_ok["filters_ok"]
        report["testnet_user_stream_possible"] = report["testnet_keys_present"]
        service = AccountPositionService(
            settings=settings,
            broker=broker,
            dry_run=settings.trading_dry_run,
            order_execution_enabled=settings.order_execution_enabled,
            allow_dry_run_flat_profile=False,
        )
        account_snapshot = await service.refresh_all(
            settings.symbols.enabled_symbols,
            latest_prices,
        )
        report["account_state_status"] = account_snapshot.account.status.value
        report["position_state_status"] = _position_status(account_snapshot)
        report["account_position_source"] = account_snapshot.source
        report["account_position_safe_for_real_order"] = account_snapshot.safe_for_real_order
        with SessionLocal() as session:
            kill_switch_enabled = CircuitBreaker(session).is_enabled()
            active_plan = get_active_strategy_plan(session)
        report["kill_switch_enabled"] = (
            settings.risk_config.kill_switch_enabled or kill_switch_enabled
        )
        report["strategy_plan_status"] = _strategy_plan_status(active_plan)
        signed_report = await _check_signed_preflight(settings)
        report["signed_account_ok"] = signed_report.get("signed_account_status") == "OK"
        report["signed_test_order_ok"] = signed_report.get("test_order_status") == "OK"
        report["signed_request_error_code"] = (
            signed_report.get("signed_account_error_code")
            or signed_report.get("test_order_error_code")
        )
        report["signed_request_error_message_sanitized"] = (
            signed_report.get("signed_account_error_message_sanitized")
            or signed_report.get("test_order_error_message_sanitized")
        )
        dq_snapshot = DataQualityGate(settings).evaluate_runtime_health(
            runtime_health={
                "state": "readiness_check",
                "market_stream_connected": filters_ok["rest_ok"],
                "user_stream_connected": report["testnet_user_stream_possible"],
                "last_kline_time": filters_ok.get("latest_kline_time"),
                "last_user_event_time": None,
                "data_delay_seconds": 0 if filters_ok["rest_ok"] else None,
            },
            exchange_filters_available=filters_ok["filters_ok"],
            account_state_status="ok"
            if account_snapshot.account.status.value == "OK"
            else "simulated_default"
            if account_snapshot.account.status.value == "SIMULATED_DEFAULT"
            else "unknown",
            position_state_status="ok"
            if report["position_state_status"] == "OK"
            else "simulated_default"
            if report["position_state_status"] == "SIMULATED_DEFAULT"
            else "unknown",
            for_real_order=True,
        )
        report["data_quality_status"] = dq_snapshot.overall_status.value
        report["data_quality_safe_for_real_order"] = dq_snapshot.safe_for_real_testnet_order
        report["budget_status"] = "OK"
        _compute_readiness(
            report,
            settings,
            dq_snapshot.safe_for_real_testnet_order,
            dq_snapshot.overall_status.value != "CRITICAL",
        )
        return report
    finally:
        await broker.client.aclose()


async def _check_rest_and_filters(
    broker: BinanceSpotTestnetBroker, settings: Settings, report: dict[str, Any]
) -> tuple[dict[str, bool], dict[str, Decimal]]:
    latest_prices: dict[str, Decimal] = {}
    try:
        await broker.client.ping()
        exchange_info = await broker.get_exchange_info()
        filters_ok = all(
            any(item.get("symbol") == symbol for item in exchange_info.get("symbols", []))
            for symbol in settings.symbols.enabled_symbols
        )
        for symbol in settings.symbols.enabled_symbols:
            ticker = await broker.client.get_symbol_price(symbol)
            latest_prices[symbol] = Decimal(str(ticker["price"]))
        klines = await broker.get_klines(settings.symbols.enabled_symbols[0], "5m", 1)
        latest_kline_time = None
        if klines:
            latest_kline_time = datetime.fromtimestamp(
                int(klines[-1][6]) / 1000,
                tz=UTC,
            ).isoformat()
        return {
            "rest_ok": True,
            "filters_ok": filters_ok,
            "latest_kline_time": latest_kline_time,
        }, latest_prices
    except Exception as exc:  # noqa: BLE001
        report["warnings"].append(f"Testnet REST/filter check failed: {type(exc).__name__}")
        return {"rest_ok": False, "filters_ok": False}, latest_prices


async def _check_signed_preflight(settings: Settings) -> dict[str, Any]:
    if not settings.binance_testnet_api_key or not settings.binance_testnet_api_secret:
        return {
            "signed_account_status": "SKIPPED",
            "test_order_status": "SKIPPED",
            "signed_account_error_code": None,
            "test_order_error_code": None,
        }
    return await run_signed_diagnostics(settings, include_test_order=True)


def _compute_readiness(
    report: dict[str, Any],
    settings: Settings,
    data_quality_safe_for_real_order: bool,
    data_quality_not_critical: bool,
) -> None:
    blockers: list[str] = []
    warnings: list[str] = report["warnings"]
    live_disabled = report["live_disabled"]
    keys = report["testnet_keys_present"]
    rest = report["testnet_rest_ok"]
    filters = report["exchange_filters_ok"]
    report["ready_for_dry_run"] = (
        settings.trading_mode == "testnet" and live_disabled and settings.trading_dry_run
    )
    report["ready_for_test_order_only"] = (
        settings.trading_mode == "testnet"
        and live_disabled
        and keys
        and rest
        and filters
        and report["signed_account_ok"]
        and data_quality_not_critical
    )
    if settings.trading_mode != "testnet":
        blockers.append("TRADING_MODE must be testnet")
    if not live_disabled:
        blockers.append("Live trading must be disabled")
    if not keys:
        blockers.append("Binance Testnet keys are missing")
    if not rest:
        blockers.append("Binance Testnet REST is not available")
    if not filters:
        blockers.append("Exchange filters are not available")
    if report["signed_request_error_code"] == -1022:
        blockers.append("BINANCE_SIGNATURE_INVALID")
    if not report["signed_account_ok"]:
        blockers.append("Signed GET account preflight failed")
    if not report["signed_test_order_ok"]:
        blockers.append("Signed POST order/test preflight failed")
    if not settings.order_execution_enabled:
        blockers.append("ORDER_EXECUTION_ENABLED=false")
    if settings.trading_dry_run:
        blockers.append("TRADING_DRY_RUN=true")
    if report["kill_switch_enabled"]:
        blockers.append("Kill switch is enabled")
    if report["account_state_status"] != "OK":
        blockers.append("Account state is not OK")
    if report["position_state_status"] != "OK":
        blockers.append("Position state is not OK")
    if not data_quality_safe_for_real_order:
        blockers.append("DataQualityGate is not safe for real Testnet order")
    if report["strategy_plan_status"] != "ACTIVE":
        warnings.append("No active StrategyPlan; runtime order path may remain no-trade.")
    report["ready_for_real_testnet_order"] = not blockers
    report["blockers"] = blockers
    report["warnings"] = warnings


def _position_status(snapshot: Any) -> str:
    statuses = {position.status.value for position in snapshot.positions}
    if not statuses:
        return "UNKNOWN"
    if statuses == {"OK"}:
        return "OK"
    if "ERROR" in statuses:
        return "ERROR"
    if "SIMULATED_DEFAULT" in statuses:
        return "SIMULATED_DEFAULT"
    return "UNKNOWN"


def _strategy_plan_status(active_plan: Any) -> str:
    if active_plan is None:
        return "UNKNOWN"
    if active_plan.requires_human_review:
        return "REQUIRES_HUMAN_REVIEW"
    return str(active_plan.status)


def save_readiness_report(report: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"testnet-readiness-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    report["report_path"] = str(path)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--save-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = asyncio.run(build_readiness_report())
    if args.save_report:
        save_readiness_report(report)
    if args.json or args.save_report:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    else:
        print(
            "ready_for_real_testnet_order="
            f"{report['ready_for_real_testnet_order']} blockers={len(report['blockers'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
