from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import UTC, datetime
from decimal import ROUND_UP, Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from account.state_service import AccountPositionService  # noqa: E402
from binance_client.exchange_info import parse_symbol_filters  # noqa: E402
from binance_client.user_stream import UserDataStreamClient  # noqa: E402
from broker.base import OrderRequest  # noqa: E402
from broker.binance_spot_testnet import BinanceSpotTestnetBroker  # noqa: E402
from config.settings import Settings, get_settings  # noqa: E402
from data_quality.gate import DataQualityGate  # noqa: E402
from journal.database import SessionLocal, init_db  # noqa: E402
from journal.models import RiskDecision  # noqa: E402
from orders.order_manager import OrderManager  # noqa: E402
from orders.reconciliation import reconcile_open_orders  # noqa: E402
from risk.circuit_breaker import CircuitBreaker  # noqa: E402
from risk.order_filter_validator import OrderFilterValidator, floor_to_step  # noqa: E402
from strategies.base import StrategySignalPayload  # noqa: E402

REPORT_DIR = ROOT / "reports" / "order_lifecycle"
TERMINAL_STATUSES = {"FILLED", "CANCELED", "REJECTED", "EXPIRED"}


def validate_lifecycle_safety(
    settings: Settings,
    *,
    confirmed: bool,
    data_quality_safe_for_real_order: bool = False,
    account_state_status: str = "UNKNOWN",
    position_state_status: str = "UNKNOWN",
    runtime_kill_switch_enabled: bool = False,
) -> list[str]:
    errors: list[str] = []
    if not confirmed:
        errors.append("Missing --i-understand-this-is-testnet confirmation flag")
    if settings.trading_mode != "testnet":
        errors.append("TRADING_MODE must be testnet")
    if settings.live_trading_enabled or settings.live_trading.enabled:
        errors.append("Live trading must be disabled")
    if not settings.order_execution_enabled:
        errors.append("ORDER_EXECUTION_ENABLED must be true for lifecycle test")
    if settings.trading_dry_run:
        errors.append("TRADING_DRY_RUN must be false for lifecycle real Testnet order")
    if not settings.binance_testnet_api_key or not settings.binance_testnet_api_secret:
        errors.append("Binance Testnet API key/secret missing")
    if settings.risk_config.kill_switch_enabled or runtime_kill_switch_enabled:
        errors.append("Kill switch must be disabled")
    if account_state_status != "OK":
        errors.append("Account state must be OK")
    if position_state_status != "OK":
        errors.append("Position state must be OK")
    if not data_quality_safe_for_real_order:
        errors.append("DataQualityGate must be safe_for_real_testnet_order")
    return errors


async def run_lifecycle(
    symbol: str, side: str, *, confirmed: bool, timeout_seconds: float
) -> dict[str, Any]:
    settings = get_settings()
    report: dict[str, Any] = {
        "report_type": "testnet_order_lifecycle",
        "created_at": datetime.now(UTC).isoformat(),
        "symbol": symbol.upper(),
        "side": side.upper(),
        "trading_mode": settings.trading_mode,
        "dry_run": settings.trading_dry_run,
        "order_execution_enabled": settings.order_execution_enabled,
        "events": [],
    }
    errors = validate_lifecycle_safety(
        settings,
        confirmed=confirmed,
        data_quality_safe_for_real_order=True,
        account_state_status="OK",
        position_state_status="OK",
    )
    if errors:
        report["status"] = "SAFETY_CHECK_FAILED"
        report["errors"] = errors
        _write_report(report)
        return report

    broker = BinanceSpotTestnetBroker(settings)
    stop_event = asyncio.Event()
    order_id: str | None = None
    try:
        exchange_info = await broker.get_exchange_info()
        filters = parse_symbol_filters(exchange_info, symbol)
        ticker = await broker.client.get_symbol_price(symbol)
        latest_price = Decimal(str(ticker["price"]))
        service = AccountPositionService(
            settings=settings,
            broker=broker,
            dry_run=settings.trading_dry_run,
            order_execution_enabled=settings.order_execution_enabled,
        )
        account_position = await service.refresh_all([symbol], {symbol.upper(): latest_price})
        with SessionLocal() as session:
            runtime_kill_switch_enabled = CircuitBreaker(session).is_enabled()
        data_quality = DataQualityGate(settings).evaluate_runtime_health(
            runtime_health={
                "state": "lifecycle_preflight",
                "market_stream_connected": True,
                "user_stream_connected": True,
                "last_kline_time": datetime.now(UTC).isoformat(),
                "last_user_event_time": datetime.now(UTC).isoformat(),
                "data_delay_seconds": 0,
            },
            exchange_filters_available=True,
            account_state_status="ok"
            if account_position.account.status.value == "OK"
            else "unknown",
            position_state_status="ok"
            if all(position.status.value == "OK" for position in account_position.positions)
            else "unknown",
            for_real_order=True,
        )
        position_status = (
            "OK"
            if all(position.status.value == "OK" for position in account_position.positions)
            else "UNKNOWN"
        )
        preflight_errors = validate_lifecycle_safety(
            settings,
            confirmed=confirmed,
            data_quality_safe_for_real_order=data_quality.safe_for_real_testnet_order,
            account_state_status=account_position.account.status.value,
            position_state_status=position_status,
            runtime_kill_switch_enabled=runtime_kill_switch_enabled,
        )
        report["preflight"] = {
            "account_state_status": account_position.account.status.value,
            "position_state_status": position_status,
            "data_quality_status": data_quality.overall_status.value,
            "data_quality_safe_for_real_testnet_order": (
                data_quality.safe_for_real_testnet_order
            ),
            "runtime_kill_switch_enabled": runtime_kill_switch_enabled,
        }
        if preflight_errors:
            report["status"] = "SAFETY_CHECK_FAILED"
            report["errors"] = preflight_errors
            return report
        order_price = _away_from_market_price(latest_price, side, filters.tick_size)
        quantity = _small_quantity(order_price, filters.min_notional, filters.step_size)
        OrderFilterValidator(filters).assert_order(price=order_price, quantity=quantity)
        request = OrderRequest(
            symbol=symbol,
            side=side,
            order_type="LIMIT",
            price=order_price,
            quantity=quantity,
            client_order_id=f"life-{uuid.uuid4().hex[:18]}",
        )
        report["order_summary"] = {
            "symbol": request.symbol,
            "side": request.side,
            "type": request.order_type,
            "price": str(request.price),
            "quantity": str(request.quantity),
            "notional": str(request.price * request.quantity if request.price else Decimal("0")),
            "trading_mode": settings.trading_mode,
            "dry_run": settings.trading_dry_run,
            "order_execution_enabled": settings.order_execution_enabled,
        }
        print(json.dumps(report["order_summary"], indent=2, ensure_ascii=False))
        await broker.test_order(request)
        init_db()
        with SessionLocal() as session:
            risk = RiskDecision(
                symbol=symbol,
                approved=True,
                reason="manual lifecycle Testnet safety checks passed",
                risk_state_json={"manual_lifecycle": True},
            )
            session.add(risk)
            session.flush()
            order_record = await OrderManager(
                broker=broker, session=session, trading_mode="testnet"
            ).submit_order(
                signal=_manual_signal(symbol, side),
                risk_decision=risk,
                order_request=request,
                dry_run=False,
                order_execution_enabled=True,
                precheck_test_order=False,
            )
            session.commit()
            order_id = order_record.exchange_order_id
            report["order_record"] = {
                "id": order_record.id,
                "client_order_id": order_record.client_order_id,
                "exchange_order_id": order_id,
                "status": order_record.status,
            }
        await _listen_user_stream(
            settings, request.client_order_id or "", report, stop_event, timeout_seconds
        )
        final = await _finalize_order(broker, symbol, order_id)
        report["final_rest_status"] = final
        with SessionLocal() as session:
            updated = await reconcile_open_orders(broker=broker, session=session)
            session.commit()
        report["reconciliation_updated"] = updated
        report["status"] = "COMPLETE"
        return report
    except Exception as exc:  # noqa: BLE001
        report["status"] = "FAILED"
        report["error"] = str(exc)
        if order_id:
            try:
                report["cancel_after_error"] = await broker.cancel_order(symbol, order_id)
            except Exception as cancel_exc:  # noqa: BLE001
                report["cancel_after_error_failed"] = str(cancel_exc)
        return report
    finally:
        stop_event.set()
        await broker.client.aclose()
        _write_report(report)


async def _listen_user_stream(
    settings: Settings,
    client_order_id: str,
    report: dict[str, Any],
    stop_event: asyncio.Event,
    timeout_seconds: float,
) -> None:
    assert settings.binance_testnet_api_key is not None
    assert settings.binance_testnet_api_secret is not None
    stream = UserDataStreamClient(
        ws_api_base=settings.binance_spot_testnet_ws_api_base,
        api_key=settings.binance_testnet_api_key,
        api_secret=settings.binance_testnet_api_secret,
    )

    async def consume() -> None:
        async for event in stream.events(stop_event):
            report["events"].append(event)
            is_target_execution = (
                event.get("e") == "executionReport" and event.get("c") == client_order_id
            )
            is_relevant_status = event.get("X") in TERMINAL_STATUSES | {"NEW", "PARTIALLY_FILLED"}
            if is_target_execution and is_relevant_status:
                stop_event.set()
                return

    task = asyncio.create_task(consume())
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=timeout_seconds)
    except TimeoutError:
        report["user_stream_timeout"] = True
    finally:
        stop_event.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def _finalize_order(
    broker: BinanceSpotTestnetBroker, symbol: str, order_id: str | None
) -> dict[str, Any] | None:
    if not order_id:
        return None
    latest = await broker.get_order(symbol, order_id)
    if latest.get("status") not in TERMINAL_STATUSES:
        cancel = await broker.cancel_order(symbol, order_id)
        latest = await broker.get_order(symbol, order_id)
        latest["cancel_response"] = cancel
    return latest


def _away_from_market_price(price: Decimal, side: str, tick_size: Decimal) -> Decimal:
    multiplier = Decimal("0.95") if side == "BUY" else Decimal("1.05")
    return floor_to_step(price * multiplier, tick_size)


def _small_quantity(price: Decimal, min_notional: Decimal, step_size: Decimal) -> Decimal:
    raw = (min_notional * Decimal("1.05")) / price
    return (raw / step_size).to_integral_value(rounding=ROUND_UP) * step_size


def _manual_signal(symbol: str, side: str) -> StrategySignalPayload:
    return StrategySignalPayload(
        symbol=symbol,
        strategy_name="manual_lifecycle",
        strategy_version="v1.0",
        timeframe="manual",
        side=side,
        signal_type="MANUAL_TESTNET_LIFECYCLE",
        confidence=1,
        reason="Manual Testnet lifecycle validation.",
        raw_payload_json={"manual": True},
    )


def _write_report(report: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"order-lifecycle-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    report["report_path"] = str(path)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTCUSDT", choices=["BTCUSDT", "ETHUSDT"])
    parser.add_argument("--side", default="BUY", choices=["BUY", "SELL"])
    parser.add_argument("--timeout-seconds", type=float, default=30)
    parser.add_argument("--i-understand-this-is-testnet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = asyncio.run(
        run_lifecycle(
            args.symbol,
            args.side,
            confirmed=args.i_understand_this_is_testnet,
            timeout_seconds=args.timeout_seconds,
        )
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if report.get("status") == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
