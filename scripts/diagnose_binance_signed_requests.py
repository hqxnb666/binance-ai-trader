from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import UTC, datetime
from decimal import ROUND_UP, Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from binance_client.errors import BinanceAPIError  # noqa: E402
from binance_client.exchange_info import SymbolFilters, parse_symbol_filters  # noqa: E402
from binance_client.signing import current_timestamp_ms  # noqa: E402
from broker.base import OrderRequest  # noqa: E402
from broker.binance_spot_testnet import BinanceSpotTestnetBroker  # noqa: E402
from config.settings import Settings, get_settings  # noqa: E402
from risk.order_filter_validator import OrderFilterValidator, floor_to_step  # noqa: E402

REPORT_DIR = ROOT / "reports" / "diagnostics"


async def run_signed_diagnostics(
    settings: Settings | None = None,
    *,
    include_test_order: bool = False,
) -> dict[str, Any]:
    settings = settings or get_settings()
    api_key_value = (
        settings.binance_testnet_api_key.get_secret_value()
        if settings.binance_testnet_api_key
        else ""
    )
    has_key = bool(settings.binance_testnet_api_key)
    has_secret = bool(settings.binance_testnet_api_secret)
    report: dict[str, Any] = {
        "report_type": "binance_signed_request_diagnostics",
        "created_at": datetime.now(UTC).isoformat(),
        "trading_mode": settings.trading_mode,
        "testnet_keys_present": has_key and has_secret,
        "api_key_preview": _preview_key(api_key_value) if has_key else "missing",
        "api_secret_present": has_secret,
        "server_time_ok": False,
        "local_time_ms": current_timestamp_ms(),
        "server_time_ms": None,
        "time_offset_ms": None,
        "recv_window": 5000,
        "signed_account_status": "SKIPPED",
        "signed_account_error_code": None,
        "signed_account_error_message_sanitized": None,
        "test_order_status": "SKIPPED",
        "test_order_error_code": None,
        "test_order_error_message_sanitized": None,
        "suspected_causes": [],
        "recommended_next_action": [],
        "safe_to_continue_test_order": False,
        "safe_to_continue_real_order": False,
    }
    if settings.trading_mode != "testnet":
        report["suspected_causes"].append("TRADING_MODE is not testnet")
    broker = BinanceSpotTestnetBroker(settings)
    try:
        await _check_server_time(broker, report)
        if not has_key or not has_secret:
            report["recommended_next_action"].append("Configure Binance Spot Testnet key/secret.")
            return report
        account_ok = await _check_signed_account(broker, report)
        if include_test_order:
            if account_ok:
                await _check_test_order(broker, settings, report)
            else:
                report["test_order_status"] = "SKIPPED"
                report["recommended_next_action"].append(
                    "Fix signed GET account before diagnosing order/test."
                )
        report["safe_to_continue_test_order"] = account_ok and (
            not include_test_order or report["test_order_status"] == "OK"
        )
        if _has_signature_error(report):
            report["suspected_causes"].append("BINANCE_SIGNATURE_INVALID")
            report["recommended_next_action"].append(
                "Verify Testnet API secret, timestamp/recvWindow, and signed parameter encoding."
            )
        elif report["signed_account_status"] == "OK" and (
            not include_test_order or report["test_order_status"] == "OK"
        ):
            report["recommended_next_action"].append(
                "Signed Testnet request path is healthy for safe test_order validation."
            )
        return report
    finally:
        await broker.client.aclose()


async def _check_server_time(
    broker: BinanceSpotTestnetBroker,
    report: dict[str, Any],
) -> None:
    try:
        server_time = await broker.client.get_time()
        server_time_ms = int(server_time["serverTime"])
        local_time_ms = current_timestamp_ms()
        report["server_time_ok"] = True
        report["local_time_ms"] = local_time_ms
        report["server_time_ms"] = server_time_ms
        report["time_offset_ms"] = server_time_ms - local_time_ms
    except Exception as exc:  # noqa: BLE001
        report["server_time_error"] = _sanitize_message(str(exc))
        report["recommended_next_action"].append("Check Binance Testnet REST connectivity.")


async def _check_signed_account(
    broker: BinanceSpotTestnetBroker,
    report: dict[str, Any],
) -> bool:
    try:
        await broker.get_account()
    except BinanceAPIError as exc:
        report["signed_account_status"] = "FAILED"
        report["signed_account_error_code"] = exc.code
        report["signed_account_error_message_sanitized"] = _sanitize_message(exc.message)
        return False
    except Exception as exc:  # noqa: BLE001
        report["signed_account_status"] = "FAILED"
        report["signed_account_error_message_sanitized"] = _sanitize_message(str(exc))
        return False
    report["signed_account_status"] = "OK"
    return True


async def _check_test_order(
    broker: BinanceSpotTestnetBroker,
    settings: Settings,
    report: dict[str, Any],
) -> bool:
    try:
        request = await build_safe_test_order(broker, settings)
        await broker.test_order(request)
    except BinanceAPIError as exc:
        report["test_order_status"] = "FAILED"
        report["test_order_error_code"] = exc.code
        report["test_order_error_message_sanitized"] = _sanitize_message(exc.message)
        return False
    except Exception as exc:  # noqa: BLE001
        report["test_order_status"] = "FAILED"
        report["test_order_error_message_sanitized"] = _sanitize_message(str(exc))
        return False
    report["test_order_status"] = "OK"
    return True


async def build_safe_test_order(
    broker: BinanceSpotTestnetBroker,
    settings: Settings,
    *,
    symbol: str | None = None,
) -> OrderRequest:
    symbol = (symbol or settings.symbols.enabled_symbols[0]).upper()
    exchange_info = await broker.get_exchange_info()
    filters = parse_symbol_filters(exchange_info, symbol)
    ticker = await broker.client.get_symbol_price(symbol)
    latest_price = Decimal(str(ticker["price"]))
    price = floor_to_step(latest_price * Decimal("0.95"), filters.tick_size)
    quantity = _minimum_test_quantity(price, filters)
    OrderFilterValidator(filters).assert_order(price=price, quantity=quantity)
    return OrderRequest(
        symbol=symbol,
        side="BUY",
        order_type="LIMIT",
        quantity=quantity,
        price=price,
        client_order_id=f"diag-{datetime.now(UTC).strftime('%H%M%S%f')}",
    )


def _minimum_test_quantity(price: Decimal, filters: SymbolFilters) -> Decimal:
    raw = (filters.min_notional * Decimal("1.05")) / price
    if raw < filters.min_qty:
        raw = filters.min_qty
    return (raw / filters.step_size).to_integral_value(rounding=ROUND_UP) * filters.step_size


def _has_signature_error(report: dict[str, Any]) -> bool:
    return report.get("signed_account_error_code") == -1022 or report.get(
        "test_order_error_code"
    ) == -1022


def _preview_key(value: str) -> str:
    if len(value) <= 8:
        return "present"
    return f"{value[:4]}****{value[-4:]}"


def _sanitize_message(message: str) -> str:
    message = re.sub(r"signature=[A-Fa-f0-9]+", "signature=<redacted>", message)
    message = re.sub(r"X-MBX-APIKEY[:=]\s*[^,\s]+", "X-MBX-APIKEY=<redacted>", message)
    return message.replace("\n", " ")[:300]


def save_report(report: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"binance-signed-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    report["report_path"] = str(path)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--testnet", action="store_true", help="Run diagnostics against Testnet.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--save-report", action="store_true")
    parser.add_argument("--include-test-order", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.testnet:
        print("Only --testnet diagnostics are supported by this script.", file=sys.stderr)
        return 2
    report = asyncio.run(run_signed_diagnostics(include_test_order=args.include_test_order))
    if args.save_report:
        save_report(report)
    if args.json or args.save_report:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    else:
        print(
            "signed_account_status="
            f"{report['signed_account_status']} test_order_status={report['test_order_status']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
