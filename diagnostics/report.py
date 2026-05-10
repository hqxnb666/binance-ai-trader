from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai.budget_guard import budget_status
from config.settings import get_settings
from data_quality.report_store import latest_data_quality_report, summarize_data_quality_report
from diagnostics.binance_access import (
    check_binance_global_rest,
    check_binance_global_ws,
    check_binance_testnet_rest,
    check_binance_testnet_ws,
)
from diagnostics.environment import collect_environment
from diagnostics.openai_access import check_openai_api
from diagnostics.proxy_detection import proxy_env_present
from journal.audit_store import get_latest_trading_issue_report
from journal.database import session_scope

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "diagnostics"


async def run_diagnostics(*, include_openai: bool = True) -> dict[str, Any]:
    settings = get_settings()
    environment = collect_environment()
    global_rest, testnet_rest, global_ws, testnet_ws = await asyncio.gather(
        check_binance_global_rest(),
        check_binance_testnet_rest(),
        check_binance_global_ws(),
        check_binance_testnet_ws(),
    )
    openai = (
        await asyncio.to_thread(check_openai_api, settings)
        if include_openai
        else {"status": "SKIPPED", "details": "OpenAI check skipped"}
    )
    connectivity = {
        "binance_global_rest": global_rest,
        "binance_testnet_rest": testnet_rest,
        "binance_global_ws": global_ws,
        "binance_testnet_ws": testnet_ws,
        "openai_api": openai,
    }
    report = {
        "environment": environment,
        "connectivity": connectivity,
        "openai_budget": _openai_budget(settings),
        "latest_audit_summary": _latest_audit_summary(),
        "latest_data_quality_summary": _latest_data_quality_summary(settings),
        "readiness": _readiness(environment, connectivity, settings.order_execution_enabled),
        "recommended_next_action": _recommend(environment, connectivity),
        "created_at": datetime.now(UTC).isoformat(),
    }
    return report


def _latest_audit_summary() -> dict[str, Any]:
    try:
        with session_scope() as session:
            latest = get_latest_trading_issue_report(session)
            if latest is None:
                return {
                    "latest_overall_status": "UNKNOWN",
                    "latest_highest_severity": "UNKNOWN",
                    "latest_issue_count": 0,
                    "latest_report_created_at": None,
                }
            return {
                "latest_overall_status": latest.overall_status,
                "latest_highest_severity": latest.highest_severity,
                "latest_issue_count": latest.issue_count,
                "latest_report_created_at": latest.created_at.isoformat(),
            }
    except Exception as exc:  # noqa: BLE001 - diagnostics must not crash if DB is absent
        return {
            "latest_overall_status": "UNKNOWN",
            "latest_highest_severity": "UNKNOWN",
            "latest_issue_count": 0,
            "latest_report_created_at": None,
            "warning": f"Audit table unavailable: {type(exc).__name__}",
        }


def _latest_data_quality_summary(settings: Any) -> dict[str, Any]:
    try:
        return summarize_data_quality_report(latest_data_quality_report(settings))
    except Exception as exc:  # noqa: BLE001 - diagnostics must stay available
        return {
            "overall_status": "UNKNOWN",
            "safe_for_signal_review": None,
            "safe_for_order": None,
            "issue_count": 0,
            "latest_created_at": None,
            "warning": f"Data quality report unavailable: {type(exc).__name__}",
        }


def _openai_budget(settings: Any) -> dict[str, Any]:
    try:
        with session_scope() as session:
            status = budget_status(settings, session)
    except Exception as exc:  # noqa: BLE001 - diagnostics must not crash if DB is absent
        status = budget_status(settings, None)
        status["warning"] = f"OpenAI usage ledger unavailable: {type(exc).__name__}"
    return {
        "enabled": settings.enable_budget_guard,
        "daily_budget_usd": settings.openai_daily_budget_usd,
        "monthly_budget_usd": settings.openai_monthly_budget_usd,
        "estimated_today_cost_usd": status.get("openai_today_cost_usd"),
        "estimated_month_cost_usd": status.get("openai_month_cost_usd"),
        "strategy_calls_today": status.get("strategy_calls_today"),
        "signal_calls_today": status.get("signal_calls_today"),
        "warning": status.get("warning"),
    }


def save_diagnostics_report(report: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"diagnostics-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def _readiness(
    environment: dict[str, Any], connectivity: dict[str, Any], order_execution_enabled: bool
) -> dict[str, bool]:
    testnet_rest_ok = connectivity["binance_testnet_rest"]["status"] == "OK"
    openai_ok = connectivity["openai_api"]["status"] == "OK"
    has_testnet_keys = (
        environment["required_env"]["BINANCE_TESTNET_API_KEY"] == "present"
        and environment["required_env"]["BINANCE_TESTNET_API_SECRET"] == "present"
    )
    return {
        "can_run_backtest_from_binance_rest": testnet_rest_ok,
        "can_run_testnet_smoke": testnet_rest_ok and has_testnet_keys,
        "can_run_with_ai": openai_ok,
        "can_place_testnet_order_if_enabled": (
            testnet_rest_ok and has_testnet_keys and order_execution_enabled
        ),
        "can_enable_live": False,
    }


def _recommend(environment: dict[str, Any], connectivity: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    testnet_status = connectivity["binance_testnet_rest"]["status"]
    openai_status = connectivity["openai_api"]["status"]
    if proxy_env_present(environment["proxy_env"]):
        actions.append(
            environment.get("proxy_warning", "Proxy env present; verify runtime settings.")
        )
    if testnet_status == "REGION_RESTRICTED":
        actions.append(
            "Binance Testnet REST appears region-restricted; trading workflows must fail closed."
        )
    elif testnet_status != "OK":
        actions.append(
            "Binance Testnet REST is unavailable; run only local database/CSV workflows."
        )
    if openai_status != "OK":
        actions.append("OpenAI API is unavailable; use --no-ai smoke tests.")
    if openai_status == "OK" and testnet_status != "OK":
        actions.append("AI is available, but the exchange is unavailable.")
    if openai_status != "OK" and testnet_status == "OK":
        actions.append(
            "Exchange is available, but AI is unavailable; --no-ai smoke test can continue."
        )
    if not actions:
        actions.append("Diagnostics look ready for Testnet smoke test. Keep Live disabled.")
    return actions
