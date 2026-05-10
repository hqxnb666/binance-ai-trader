from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_UP, Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.schemas import (  # noqa: E402
    MarketRegime,
    RiskLevel,
    SignalDecision,
    SignalReview,
    SignalSide,
)
from ai.signal_reviewer import SignalReviewer  # noqa: E402
from binance_client.errors import BinanceAPIError  # noqa: E402
from binance_client.exchange_info import SymbolFilters, parse_symbol_filters  # noqa: E402
from broker.base import OrderRequest  # noqa: E402
from broker.binance_spot_testnet import BinanceSpotTestnetBroker  # noqa: E402
from config.settings import Settings, get_settings  # noqa: E402
from data_quality.gate import DataQualityGate  # noqa: E402
from data_quality.schemas import DataQualitySeverity  # noqa: E402
from diagnostics.report import run_diagnostics  # noqa: E402
from features.indicators import calculate_indicators  # noqa: E402
from features.kline_store import binance_klines_to_dataframe  # noqa: E402
from features.market_snapshot import build_market_snapshot  # noqa: E402
from journal.database import SessionLocal, init_db  # noqa: E402
from journal.models import MarketKline, RiskDecision  # noqa: E402
from orders.order_manager import OrderManager  # noqa: E402
from orders.reconciliation import reconcile_open_orders  # noqa: E402
from risk.position_sizer import PositionSizer  # noqa: E402
from risk.risk_engine import AccountState, MarketHealth, PositionState, RiskEngine  # noqa: E402
from scripts.verify_testnet_order_readiness import build_readiness_report  # noqa: E402
from strategies.base import StrategySignalPayload  # noqa: E402
from strategies.ema_trend import EmaTrendStrategy  # noqa: E402

REPORT_DIR = ROOT / "reports" / "smoke_tests"
ENV_PATH = ROOT / ".env"


@dataclass(frozen=True)
class SmokeOptions:
    check_config_only: bool = False
    with_ai: bool = False
    test_order_only: bool = False
    allow_real_testnet_order: bool = False


def build_preflight_report(settings: Settings) -> dict[str, Any]:
    return {
        "env_file_exists": ENV_PATH.exists(),
        "has_binance_testnet_key": bool(settings.binance_testnet_api_key),
        "has_binance_testnet_secret": bool(settings.binance_testnet_api_secret),
        "has_openai_key": bool(settings.openai_api_key),
        "trading_mode": settings.trading_mode,
        "live_trading_enabled": settings.live_trading_enabled,
        "config_live_trading_enabled": settings.live_trading.enabled,
        "dry_run": settings.trading_dry_run,
        "order_execution_enabled": settings.order_execution_enabled,
    }


async def smoke_test(
    check_config_only: bool = False,
    *,
    with_ai: bool = False,
    test_order_only: bool = False,
    allow_real_testnet_order: bool = False,
) -> dict[str, Any]:
    options = SmokeOptions(
        check_config_only=check_config_only,
        with_ai=with_ai,
        test_order_only=test_order_only,
        allow_real_testnet_order=allow_real_testnet_order,
    )
    settings = get_settings()
    report: dict[str, Any] = {
        "report_type": "testnet_smoke_test",
        "created_at": datetime.now(UTC).isoformat(),
        "options": options.__dict__,
        "stages": [],
    }

    stage0 = _stage("Stage 0: Config check")
    stage0["summary"] = build_preflight_report(settings)
    config_error = _config_error(stage0["summary"], require_openai=with_ai)
    if check_config_only:
        stage0["ok"] = config_error is None
        if config_error:
            stage0["error"] = config_error
        report["stages"].append(stage0)
        report["status"] = "CONFIG_ONLY"
        _write_report(report)
        return report
    if config_error:
        stage0.update({"ok": False, "error": config_error})
        report["stages"].append(stage0)
        report["status"] = "CONFIG_FAILED"
        _write_report(report)
        return report
    stage0["ok"] = True
    report["stages"].append(stage0)

    diagnostics = await run_diagnostics(include_openai=with_ai)
    report["diagnostics_summary"] = _diagnostics_summary(diagnostics)
    gate_error = _diagnostics_gate_error(diagnostics, with_ai=with_ai)
    if gate_error:
        report["status"] = "DIAGNOSTICS_FAILED"
        report["error"] = gate_error
        _write_report(report)
        return report
    if diagnostics["connectivity"]["binance_testnet_ws"]["status"] != "OK":
        report.setdefault("warnings", []).append(
            "Binance Testnet WebSocket unavailable; continuing REST-only smoke path."
        )

    broker = BinanceSpotTestnetBroker(settings)
    try:
        _exchange_info, filters = await _stage1_rest(report, broker, settings)
        frames = await _stage2_market_data(report, broker, settings)
        signal, snapshot = _build_signal_and_snapshot(settings, frames)
        report["snapshot"] = snapshot
        data_quality = _stage2_5_data_quality(
            report,
            settings,
            frames,
            filters,
            snapshot,
            require_real_order=allow_real_testnet_order or test_order_only,
        )
        if data_quality["overall_status"] == DataQualitySeverity.CRITICAL.value:
            report["status"] = "DATA_QUALITY_BLOCKED"
            report["error"] = "DataQualityGate blocked smoke test before AI/order stages."
            return report
        review, schema_valid = await _stage3_ai(report, settings, snapshot, with_ai)
        if not schema_valid:
            report["status"] = "AI_SCHEMA_FAILED"
            return report
        risk_decision, sized = _stage4_risk(report, settings, filters, signal, snapshot, review)
        if not risk_decision.approved:
            report["status"] = "RISK_REJECTED"
            return report
        if test_order_only or allow_real_testnet_order:
            readiness_ok = await _readiness_gate(report, allow_real_testnet_order)
            if not readiness_ok:
                report["status"] = "READINESS_BLOCKED"
                return report
        test_order_ok = await _stage5_test_order(report, broker, signal, sized)
        if not test_order_ok or test_order_only or not allow_real_testnet_order:
            report["status"] = report.get("test_order_failure_status", "TEST_ORDER_COMPLETE")
            if not allow_real_testnet_order:
                report["real_order"] = "Skipped: --allow-real-testnet-order was not provided."
            return report
        await _stage6_real_testnet_order(report, broker, settings, signal, risk_decision, sized)
        report["status"] = "REAL_TESTNET_ORDER_COMPLETE"
        return report
    except Exception as exc:  # noqa: BLE001 - smoke report should explain every failure
        report["status"] = "FAILED"
        report["error"] = str(exc)
        return report
    finally:
        await broker.client.aclose()
        _write_report(report)


async def _stage1_rest(
    report: dict[str, Any], broker: BinanceSpotTestnetBroker, settings: Settings
) -> tuple[dict[str, Any], dict[str, SymbolFilters]]:
    stage = _stage("Stage 1: Binance REST connectivity")
    await broker.client.ping()
    server_time = await broker.client.get_time()
    exchange_info = await broker.get_exchange_info()
    filters = {
        symbol: parse_symbol_filters(exchange_info, symbol)
        for symbol in settings.symbols.enabled_symbols
    }
    stage.update(
        {
            "ok": True,
            "server_time": server_time,
            "symbols_checked": list(filters),
            "filters": {
                symbol: {
                    "tick_size": str(item.tick_size),
                    "step_size": str(item.step_size),
                    "min_notional": str(item.min_notional),
                }
                for symbol, item in filters.items()
            },
        }
    )
    report["stages"].append(stage)
    return exchange_info, filters


async def _stage2_market_data(
    report: dict[str, Any], broker: BinanceSpotTestnetBroker, settings: Settings
) -> dict[tuple[str, str], Any]:
    stage = _stage("Stage 2: Market data")
    init_db()
    frames = {}
    with SessionLocal() as session:
        for symbol in settings.symbols.enabled_symbols:
            klines_5m = await broker.get_klines(symbol, "5m", 300)
            klines_1h = await broker.get_klines(symbol, "1h", 100)
            frames[(symbol, "5m")] = binance_klines_to_dataframe(klines_5m)
            frames[(symbol, "1h")] = binance_klines_to_dataframe(klines_1h)
            _persist_rest_klines(session, symbol, "5m", klines_5m)
            _persist_rest_klines(session, symbol, "1h", klines_1h)
        session.commit()
    indicators = {
        symbol: calculate_indicators(frames[(symbol, "5m")])
        for symbol in settings.symbols.enabled_symbols
    }
    stage.update({"ok": True, "indicators": indicators})
    report["stages"].append(stage)
    return frames


def _stage2_5_data_quality(
    report: dict[str, Any],
    settings: Settings,
    frames: dict[tuple[str, str], Any],
    filters: dict[str, SymbolFilters],
    snapshot: dict[str, Any],
    *,
    require_real_order: bool,
) -> dict[str, Any]:
    stage = _stage("Stage 2.5: DataQualityGate")
    symbol = str(snapshot.get("symbol", settings.symbols.enabled_symbols[0]))
    data_quality = DataQualityGate(settings).evaluate_runtime_health(
        runtime_health={
            "state": "smoke_test",
            "market_stream_connected": True,
            "user_stream_connected": (
                not require_real_order or bool(settings.binance_testnet_api_key)
            ),
            "last_kline_time": frames[(symbol, "5m")]["close_time"].iloc[-1].isoformat(),
            "last_user_event_time": None,
            "data_delay_seconds": snapshot.get("data_delay_seconds", 0),
        },
        exchange_filters_available=symbol in filters,
        account_state_status="unknown" if require_real_order else "simulated_default",
        position_state_status="unknown" if require_real_order else "simulated_default",
        indicator_nan_count=sum(
            1
            for key in (
                "ema_fast_5m",
                "ema_slow_5m",
                "ema_fast_1h",
                "ema_slow_1h",
                "rsi14_5m",
                "atr14_5m",
                "volume_ratio_5m",
            )
            if snapshot.get(key) is None
        ),
        kline_count=min(len(frames[(symbol, "5m")]), len(frames[(symbol, "1h")])),
        for_real_order=require_real_order and settings.order_execution_enabled,
    )
    payload = data_quality.model_dump(mode="json")
    stage.update(
        {
            "ok": data_quality.overall_status != DataQualitySeverity.CRITICAL,
            "overall_status": data_quality.overall_status.value,
            "safe_for_signal_review": data_quality.safe_for_signal_review,
            "safe_for_order": data_quality.safe_for_order,
            "account_state_status": data_quality.account_state_status,
            "position_state_status": data_quality.position_state_status,
            "issues": payload["issues"],
            "reason_codes": data_quality.reason_codes,
        }
    )
    report["stages"].append(stage)
    return payload


async def _stage3_ai(
    report: dict[str, Any],
    settings: Settings,
    snapshot: dict[str, Any],
    with_ai: bool,
) -> tuple[SignalReview, bool]:
    stage = _stage("Stage 3: OpenAI structured output")
    if with_ai:
        result = await asyncio.to_thread(SignalReviewer(settings).review_with_schema, snapshot)
        review = result.review
        schema_valid = result.schema_valid
        stage.update(
            {
                "ok": schema_valid,
                "called_openai": True,
                "reason": result.reason,
                "review": review.model_dump(mode="json"),
            }
        )
    else:
        review = SignalReview(
            decision=SignalDecision.APPROVE_TO_RISK_ENGINE,
            symbol=str(snapshot["symbol"]),
            side=SignalSide.BUY,
            confidence=0.75,
            risk_level=RiskLevel.LOW,
            market_regime=MarketRegime.TREND_UP,
            reason="Smoke test no-ai local schema-valid review.",
            warnings=["OpenAI was not called."],
            max_position_pct=1,
            requires_human_review=False,
        )
        schema_valid = True
        stage.update({"ok": True, "called_openai": False, "review": review.model_dump(mode="json")})
    report["stages"].append(stage)
    return review, schema_valid


def _stage4_risk(
    report: dict[str, Any],
    settings: Settings,
    filters: dict[str, SymbolFilters],
    signal: StrategySignalPayload,
    snapshot: dict[str, Any],
    review: SignalReview,
):
    stage = _stage("Stage 4: RiskEngine")
    sized = _size_smoke_order(settings, filters[signal.symbol], Decimal(str(snapshot["price"])))
    decision = RiskEngine(settings).evaluate(
        signal=signal,
        ai_review=review,
        ai_schema_valid=True,
        account=AccountState(equity_usdt=Decimal("1000")),
        position=PositionState(symbol=signal.symbol),
        market_health=MarketHealth(
            ws_connected=True,
            market_stream_connected=True,
            user_stream_connected=True,
            data_delay_seconds=0,
        ),
        symbol_filters=filters[signal.symbol],
        order_price=sized.adjusted_entry_price,
        order_quantity=sized.adjusted_quantity,
        trading_mode="testnet",
        client_order_id=f"smoke-risk-{uuid.uuid4().hex[:12]}",
    )
    stage.update(
        {
            "ok": decision.approved,
            "approved": decision.approved,
            "reason": decision.reason,
            "order_price": str(sized.adjusted_entry_price),
            "order_quantity": str(sized.adjusted_quantity),
            "notional": str(sized.notional),
        }
    )
    report["stages"].append(stage)
    return decision, sized


async def _stage5_test_order(
    report: dict[str, Any],
    broker: BinanceSpotTestnetBroker,
    signal: StrategySignalPayload,
    sized: Any,
) -> bool:
    stage = _stage("Stage 5: Binance test_order")
    request = _order_request(signal.symbol, signal.side, sized)
    try:
        await broker.test_order(request)
    except BinanceAPIError as exc:
        stage.update(
            {
                "ok": False,
                "error_code": exc.code,
                "error": exc.message,
            }
        )
        if exc.code == -1022:
            stage["status"] = "TEST_ORDER_SIGNATURE_FAILED"
            stage["recommended_next_action"] = (
                "Run python scripts/diagnose_binance_signed_requests.py "
                "--testnet --include-test-order --json"
            )
            report["test_order_failure_status"] = "TEST_ORDER_SIGNATURE_FAILED"
        report["stages"].append(stage)
        return False
    except Exception as exc:  # noqa: BLE001
        stage.update({"ok": False, "error": str(exc)})
        report["stages"].append(stage)
        return False
    stage.update(
        {
            "ok": True,
            "symbol": request.symbol,
            "side": request.side,
            "order_type": request.order_type,
            "price": str(request.price),
            "quantity": str(request.quantity),
        }
    )
    report["stages"].append(stage)
    return True


async def _readiness_gate(report: dict[str, Any], allow_real_testnet_order: bool) -> bool:
    stage = _stage("Stage 4.5: Testnet order readiness")
    readiness = await build_readiness_report()
    required_key = (
        "ready_for_real_testnet_order"
        if allow_real_testnet_order
        else "ready_for_test_order_only"
    )
    ok = bool(readiness.get(required_key))
    stage.update(
        {
            "ok": ok,
            "required": required_key,
            "ready_for_dry_run": readiness.get("ready_for_dry_run"),
            "ready_for_test_order_only": readiness.get("ready_for_test_order_only"),
            "ready_for_real_testnet_order": readiness.get("ready_for_real_testnet_order"),
            "blockers": readiness.get("blockers", []),
            "warnings": readiness.get("warnings", []),
        }
    )
    report["stages"].append(stage)
    return ok


async def _stage6_real_testnet_order(
    report: dict[str, Any],
    broker: BinanceSpotTestnetBroker,
    settings: Settings,
    signal: StrategySignalPayload,
    risk_decision: Any,
    sized: Any,
) -> None:
    stage = _stage("Stage 6: Optional small Testnet order")
    if not settings.order_execution_enabled:
        stage.update({"ok": False, "error": "ORDER_EXECUTION_ENABLED=false"})
        report["stages"].append(stage)
        return
    request = _order_request(signal.symbol, signal.side, sized)
    init_db()
    with SessionLocal() as session:
        risk_record = RiskDecision(
            symbol=signal.symbol,
            approved=risk_decision.approved,
            reason=risk_decision.reason,
            risk_state_json=risk_decision.risk_state_json,
        )
        session.add(risk_record)
        session.flush()
        order_record = await OrderManager(
            broker=broker, session=session, trading_mode="testnet"
        ).submit_order(
            signal=signal,
            risk_decision=risk_record,
            order_request=request,
            dry_run=False,
            order_execution_enabled=True,
            precheck_test_order=False,
        )
        session.commit()
        final_status = None
        if order_record.exchange_order_id:
            final_status = await _wait_and_cancel_if_open(
                broker, request.symbol, order_record.exchange_order_id
            )
            await reconcile_open_orders(broker=broker, session=session)
            session.commit()
        stage.update(
            {
                "ok": True,
                "order_record": {
                    "id": order_record.id,
                    "exchange_order_id": order_record.exchange_order_id,
                    "client_order_id": order_record.client_order_id,
                    "status": order_record.status,
                },
                "final_status": final_status,
            }
        )
    report["stages"].append(stage)


async def _wait_and_cancel_if_open(
    broker: BinanceSpotTestnetBroker, symbol: str, order_id: str
) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + 30
    latest: dict[str, Any] = {}
    while asyncio.get_running_loop().time() < deadline:
        latest = await broker.get_order(symbol, order_id)
        if latest.get("status") in {"FILLED", "CANCELED", "REJECTED", "EXPIRED"}:
            return latest
        await asyncio.sleep(2)
    cancel = await broker.cancel_order(symbol, order_id)
    return {"last_query": latest, "cancel": cancel}


def _build_signal_and_snapshot(
    settings: Settings, frames: dict[tuple[str, str], Any]
) -> tuple[StrategySignalPayload, dict[str, Any]]:
    symbol = settings.symbols.enabled_symbols[0]
    entry_df = frames[(symbol, "5m")]
    trend_df = frames[(symbol, "1h")]
    strategy = EmaTrendStrategy(settings.strategy.ema_trend)
    signal = strategy.generate_signal(
        symbol=symbol,
        entry_df=entry_df,
        trend_df=trend_df,
        ws_health="ok",
    ) or StrategySignalPayload(
        symbol=symbol,
        strategy_name="ema_trend",
        strategy_version="v1.0",
        timeframe="5m",
        side="BUY",
        signal_type="SMOKE_TEST_BUY",
        confidence=0.5,
        reason="Smoke test synthetic BUY candidate for validation path.",
        raw_payload_json={"synthetic": True},
    )
    snapshot = build_market_snapshot(
        symbol=symbol,
        entry_df=entry_df,
        trend_df=trend_df,
        strategy_signal=signal,
        ws_health="ok",
    ).compact_dict()
    return signal, snapshot


def _order_request(symbol: str, side: str, sized: Any) -> OrderRequest:
    return OrderRequest(
        symbol=symbol,
        side=side,
        order_type="LIMIT",
        quantity=sized.adjusted_quantity,
        price=sized.adjusted_entry_price,
        client_order_id=f"smoke-{uuid.uuid4().hex[:18]}",
    )


def _size_smoke_order(settings: Settings, filters: SymbolFilters, price: Decimal):
    stop = price * Decimal("0.99")
    result = PositionSizer().size_position(
        account_equity_usdt=Decimal("1000"),
        max_single_trade_risk_pct=Decimal(str(settings.risk_config.max_single_trade_risk_pct)),
        entry_price=price,
        stop_loss_price=stop,
        max_position_pct_per_symbol=Decimal("1"),
        filters=filters,
    )
    min_qty = (filters.min_notional / result.adjusted_entry_price) * Decimal("1.02")
    min_qty = (min_qty / filters.step_size).to_integral_value(rounding=ROUND_UP) * filters.step_size
    if min_qty > result.adjusted_quantity:
        result = result.__class__(
            quantity=min_qty,
            notional=min_qty * result.adjusted_entry_price,
            risk_amount=result.risk_amount,
            adjusted_quantity=min_qty,
            adjusted_entry_price=result.adjusted_entry_price,
        )
    return result


def _persist_rest_klines(
    session: Any, symbol: str, timeframe: str, klines: list[list[Any]]
) -> None:
    for item in klines:
        session.add(
            MarketKline(
                symbol=symbol,
                timeframe=timeframe,
                open_time=datetime.fromtimestamp(int(item[0]) / 1000, tz=UTC),
                close_time=datetime.fromtimestamp(int(item[6]) / 1000, tz=UTC),
                open=Decimal(str(item[1])),
                high=Decimal(str(item[2])),
                low=Decimal(str(item[3])),
                close=Decimal(str(item[4])),
                volume=Decimal(str(item[5])),
                is_closed=True,
            )
        )


def _config_error(summary: dict[str, Any], *, require_openai: bool) -> str | None:
    if not summary["env_file_exists"]:
        return ".env file is missing. Copy .env.example to .env before full smoke tests."
    if summary["trading_mode"] != "testnet":
        return "TRADING_MODE must be testnet"
    if summary["live_trading_enabled"] or summary["config_live_trading_enabled"]:
        return "Live trading must remain disabled for Testnet smoke tests"
    if not summary["has_binance_testnet_key"] or not summary["has_binance_testnet_secret"]:
        return "Binance Testnet API key/secret missing"
    if require_openai and not summary["has_openai_key"]:
        return "OPENAI_API_KEY missing but --with-ai was requested"
    return None


def _diagnostics_summary(diagnostics: dict[str, Any]) -> dict[str, Any]:
    connectivity = diagnostics["connectivity"]
    return {
        "binance_testnet_rest": connectivity["binance_testnet_rest"]["status"],
        "binance_testnet_ws": connectivity["binance_testnet_ws"]["status"],
        "openai_api": connectivity["openai_api"]["status"],
        "proxy_env_present": any(
            value == "present" for value in diagnostics["environment"]["proxy_env"].values()
        ),
        "recommended_next_action": diagnostics["recommended_next_action"],
    }


def _diagnostics_gate_error(diagnostics: dict[str, Any], *, with_ai: bool) -> str | None:
    connectivity = diagnostics["connectivity"]
    rest_status = connectivity["binance_testnet_rest"]["status"]
    openai_status = connectivity["openai_api"]["status"]
    if rest_status == "REGION_RESTRICTED":
        return "Binance Testnet REST is region-restricted; smoke test fails closed."
    if rest_status != "OK":
        return f"Binance Testnet REST unavailable: {rest_status}"
    if with_ai and openai_status != "OK":
        return f"OpenAI API unavailable for --with-ai: {openai_status}"
    return None


def _stage(name: str) -> dict[str, Any]:
    return {"name": name, "started_at": datetime.now(UTC).isoformat()}


def _write_report(report: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"smoke-test-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    report["report_path"] = str(path)
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-config-only", action="store_true")
    parser.add_argument("--no-ai", action="store_true", help="Do not call OpenAI; this is default.")
    parser.add_argument("--with-ai", action="store_true", help="Call OpenAI SignalReview.")
    parser.add_argument("--test-order-only", action="store_true")
    parser.add_argument("--allow-real-testnet-order", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.no_ai and args.with_ai:
        print("--no-ai and --with-ai are mutually exclusive", file=sys.stderr)
        return 2
    report = asyncio.run(
        smoke_test(
            check_config_only=args.check_config_only,
            with_ai=args.with_ai,
            test_order_only=args.test_order_only,
            allow_real_testnet_order=args.allow_real_testnet_order,
        )
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if report.get("status") not in {"FAILED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
