from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ai.audit_schemas import AuditReportType
from ai.schemas import (
    MarketRegime,
    RiskLevel,
    SignalDecision,
    SignalReview,
    SignalSide,
    signal_review_trade_gate,
)
from app.dependencies import db_session_dependency, settings_dependency
from config.settings import Settings
from dashboard.config_service import (
    load_risk_config,
    save_strategy_config,
    strategy_config_response,
    validate_strategy_config,
)
from diagnostics.report import run_diagnostics
from journal.audit_store import (
    audit_record_to_dict,
    get_latest_trading_issue_report,
    list_recent_trading_issue_reports,
)
from journal.daily_report import build_daily_report, upsert_daily_report
from journal.models import (
    DailyReport,
    OpenAIUsageRecord,
    OrderRecord,
    PipelineAudit,
    RiskDecision,
    RuntimeState,
    StrategySignal,
)
from journal.openai_usage_store import summarize_openai_usage
from journal.pipeline_audit import pipeline_audits_by_run_id, recent_pipeline_audits
from risk.circuit_breaker import CircuitBreaker
from runtime.task_manager import RuntimeTaskManager
from scripts.verify_testnet_order_readiness import build_readiness_report

router = APIRouter()


def runtime_manager(request: Request) -> RuntimeTaskManager:
    return request.app.state.runtime_manager


@router.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "time": datetime.now(UTC).isoformat()}


@router.get("/status")
def status(
    settings: Settings = Depends(settings_dependency),
    session: Session = Depends(db_session_dependency),
) -> dict[str, object]:
    return {
        "app_env": settings.app_env,
        "trading_mode": settings.trading_mode,
        "live_trading_enabled": settings.live_trading_enabled and settings.live_trading.enabled,
        "kill_switch_enabled": CircuitBreaker(session).is_enabled(),
        "symbols": settings.symbols.enabled_symbols,
    }


@router.get("/config/safe")
def safe_config(settings: Settings = Depends(settings_dependency)) -> dict[str, object]:
    return settings.safe_config()


@router.get("/config/strategy")
def strategy_config() -> dict[str, object]:
    return strategy_config_response()


@router.post("/config/strategy/validate")
def strategy_config_validate(payload: dict[str, Any]) -> dict[str, object]:
    return validate_strategy_config(payload)


@router.post("/config/strategy/save")
def strategy_config_save(payload: dict[str, Any]) -> dict[str, object]:
    return save_strategy_config(payload)


@router.get("/config/risk")
def risk_config() -> dict[str, object]:
    return {
        "config": load_risk_config(),
        "read_only": True,
        "message": (
            "Risk config is read-only in Dashboard V2. Edit risk.yaml manually only with "
            "explicit tests and review."
        ),
    }


@router.get("/symbols")
def symbols(settings: Settings = Depends(settings_dependency)) -> dict[str, object]:
    return settings.symbols.model_dump()


@router.get("/signals/recent")
def recent_signals(
    limit: int = 25,
    session: Session = Depends(db_session_dependency),
) -> list[dict[str, object]]:
    rows = session.scalars(
        select(StrategySignal).order_by(desc(StrategySignal.created_at)).limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "symbol": row.symbol,
            "side": row.side,
            "confidence": float(row.confidence),
            "reason": row.reason,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/orders/recent")
def recent_orders(
    limit: int = 25,
    session: Session = Depends(db_session_dependency),
) -> list[dict[str, object]]:
    query = select(OrderRecord).order_by(desc(OrderRecord.created_at)).limit(limit)
    rows = session.scalars(query).all()
    return [
        {
            "id": row.id,
            "exchange_order_id": row.exchange_order_id,
            "client_order_id": row.client_order_id,
            "symbol": row.symbol,
            "side": row.side,
            "order_type": row.order_type,
            "price": str(row.price) if row.price is not None else None,
            "quantity": str(row.quantity),
            "status": row.status,
            "trading_mode": row.trading_mode,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/risk/state")
def risk_state(
    settings: Settings = Depends(settings_dependency),
    session: Session = Depends(db_session_dependency),
) -> dict[str, object]:
    last_decision = session.scalar(select(RiskDecision).order_by(desc(RiskDecision.created_at)))
    return {
        "configured": settings.risk_config.model_dump(),
        "kill_switch_enabled": CircuitBreaker(session).is_enabled(),
        "last_decision": None
        if last_decision is None
        else {
            "approved": last_decision.approved,
            "reason": last_decision.reason,
            "created_at": last_decision.created_at.isoformat(),
        },
    }


@router.get("/journal/daily")
def journal_daily(
    report_date: date | None = None,
    session: Session = Depends(db_session_dependency),
    settings: Settings = Depends(settings_dependency),
) -> dict[str, object]:
    target = report_date or date.today()
    row = session.scalar(
        select(DailyReport)
        .where(DailyReport.report_date == target)
        .order_by(desc(DailyReport.created_at))
    )
    if row is None:
        payload = build_daily_report(session, target, settings.trading_mode)
        row = upsert_daily_report(session, payload)
        session.commit()
    return {
        "report_date": row.report_date.isoformat(),
        "trading_mode": row.trading_mode,
        "total_signals": row.total_signals,
        "total_orders": row.total_orders,
        "total_trades": row.total_trades,
        "win_rate": float(row.win_rate),
        "pnl": str(row.pnl),
        "fees": str(row.fees),
        "ai_summary": row.ai_summary,
        "raw_json": row.raw_json,
    }


@router.post("/control/kill-switch/on")
def kill_switch_on(session: Session = Depends(db_session_dependency)) -> dict[str, object]:
    CircuitBreaker(session).set_enabled(True)
    session.commit()
    return {"kill_switch_enabled": True}


@router.post("/control/kill-switch/off")
def kill_switch_off(session: Session = Depends(db_session_dependency)) -> dict[str, object]:
    CircuitBreaker(session).set_enabled(False)
    session.commit()
    return {"kill_switch_enabled": False}


@router.post("/control/test-ai-review")
def test_ai_review() -> dict[str, object]:
    review = SignalReview(
        decision=SignalDecision.HUMAN_REVIEW_REQUIRED,
        symbol="BTCUSDT",
        side=SignalSide.HOLD,
        confidence=0,
        risk_level=RiskLevel.HIGH,
        market_regime=MarketRegime.UNCLEAR,
        reason="Dry-run endpoint does not call external AI.",
        warnings=["No order can be placed from this endpoint."],
        max_position_pct=0,
        requires_human_review=True,
    )
    approved, reason = signal_review_trade_gate(review)
    return {"schema_valid": True, "trade_allowed": approved, "reason": reason, "review": review}


@router.post("/control/testnet/start")
async def testnet_start(
    request: Request,
    session: Session = Depends(db_session_dependency),
) -> dict[str, object]:
    state = session.get(RuntimeState, "testnet_worker")
    if state is None:
        state = RuntimeState(key="testnet_worker", value_json={"running": True})
        session.add(state)
    else:
        state.value_json = {"running": True}
    session.commit()
    result = await runtime_manager(request).start_testnet()
    return {"testnet_worker": "running", "runtime": result}


@router.post("/control/testnet/stop")
async def testnet_stop(
    request: Request,
    session: Session = Depends(db_session_dependency),
) -> dict[str, object]:
    state = session.get(RuntimeState, "testnet_worker")
    if state is None:
        state = RuntimeState(key="testnet_worker", value_json={"running": False})
        session.add(state)
    else:
        state.value_json = {"running": False}
    session.commit()
    result = await runtime_manager(request).stop_testnet()
    return {"testnet_worker": "stopped", "runtime": result}


@router.get("/runtime/state")
def runtime_state(manager: RuntimeTaskManager = Depends(runtime_manager)) -> dict[str, object]:
    return manager.state()


@router.get("/runtime/health")
def runtime_health(manager: RuntimeTaskManager = Depends(runtime_manager)) -> dict[str, object]:
    health = manager.health()
    latest = getattr(manager, "latest_diagnostics", None)
    health["network_readiness"] = _network_readiness(latest)
    return health


@router.post("/runtime/testnet/start")
async def runtime_testnet_start(
    manager: RuntimeTaskManager = Depends(runtime_manager),
) -> dict[str, object]:
    return await manager.start_testnet()


@router.post("/runtime/testnet/stop")
async def runtime_testnet_stop(
    manager: RuntimeTaskManager = Depends(runtime_manager),
) -> dict[str, object]:
    return await manager.stop_testnet()


@router.post("/runtime/testnet/start-dry-run")
async def runtime_testnet_start_dry_run(
    manager: RuntimeTaskManager = Depends(runtime_manager),
) -> dict[str, object]:
    return await manager.start_testnet(dry_run=True, order_execution_enabled=False)


@router.post("/runtime/testnet/stop-dry-run")
async def runtime_testnet_stop_dry_run(
    manager: RuntimeTaskManager = Depends(runtime_manager),
) -> dict[str, object]:
    return await manager.stop_testnet()


@router.get("/runtime/logs/recent")
def runtime_logs_recent(
    limit: int = 100,
    manager: RuntimeTaskManager = Depends(runtime_manager),
) -> list[dict[str, object]]:
    return manager.logs(limit)


@router.get("/runtime/last-snapshots")
def runtime_last_snapshots(
    manager: RuntimeTaskManager = Depends(runtime_manager),
) -> dict[str, object]:
    return manager.last_snapshots()


@router.get("/runtime/last-ai-reviews")
def runtime_last_ai_reviews(
    manager: RuntimeTaskManager = Depends(runtime_manager),
) -> list[dict[str, object]]:
    return manager.last_ai_reviews()


@router.get("/runtime/last-risk-decisions")
def runtime_last_risk_decisions(
    manager: RuntimeTaskManager = Depends(runtime_manager),
) -> list[dict[str, object]]:
    return manager.last_risk_decisions()


@router.post("/runtime/diagnostics/run")
async def runtime_diagnostics_run(
    manager: RuntimeTaskManager = Depends(runtime_manager),
) -> dict[str, object]:
    report = await run_diagnostics()
    manager.latest_diagnostics = report
    return report


@router.get("/runtime/diagnostics/latest")
def runtime_diagnostics_latest(
    manager: RuntimeTaskManager = Depends(runtime_manager),
) -> dict[str, object]:
    latest = getattr(manager, "latest_diagnostics", None)
    if latest is None:
        return {"status": "NO_DIAGNOSTICS_RUN", "network_readiness": _network_readiness(None)}
    return latest


@router.post("/runtime/readiness/check")
async def runtime_readiness_check(
    request: Request,
    settings: Settings = Depends(settings_dependency),
) -> dict[str, object]:
    report = await build_readiness_report(settings)
    request.app.state.latest_readiness_report = report
    return report


@router.get("/runtime/readiness/latest")
def runtime_readiness_latest(request: Request) -> dict[str, object]:
    latest = getattr(request.app.state, "latest_readiness_report", None)
    if latest is None:
        return {"status": "NO_READINESS_CHECK_RUN"}
    return latest


@router.get("/runtime/openai-usage")
def runtime_openai_usage(
    days: int = 1,
    session: Session = Depends(db_session_dependency),
    settings: Settings = Depends(settings_dependency),
) -> dict[str, object]:
    days = max(1, min(days, 90))
    summary = summarize_openai_usage(session, days=days)
    since = datetime.now(UTC) - timedelta(days=days)
    rows = session.scalars(
        select(OpenAIUsageRecord).where(OpenAIUsageRecord.created_at >= since)
    ).all()
    status_breakdown: dict[str, int] = {}
    for row in rows:
        status_breakdown[row.status] = status_breakdown.get(row.status, 0) + 1
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "days": days,
        "summary": summary,
        "status_breakdown": status_breakdown,
        "daily_budget_usd": settings.openai_daily_budget_usd,
        "monthly_budget_usd": settings.openai_monthly_budget_usd,
        "warnings": _openai_usage_warnings(summary, settings),
        "safety_note": "No raw prompts, raw responses, API keys, or request headers are returned.",
    }


@router.get("/runtime/audit/recent")
def runtime_audit_recent(
    limit: int = 50,
    session: Session = Depends(db_session_dependency),
) -> list[dict[str, object]]:
    return [_audit_row(row) for row in recent_pipeline_audits(session, limit)]


@router.get("/runtime/audit/{run_id}")
def runtime_audit_by_run_id(
    run_id: str,
    session: Session = Depends(db_session_dependency),
) -> list[dict[str, object]]:
    return [_audit_row(row) for row in pipeline_audits_by_run_id(session, run_id)]


@router.get("/runtime/audits/latest")
def runtime_audits_latest(
    session: Session = Depends(db_session_dependency),
) -> dict[str, object]:
    latest = get_latest_trading_issue_report(session)
    if latest is None:
        return {"status": "NO_AUDIT_REPORT"}
    return audit_record_to_dict(latest)


@router.get("/runtime/audits/recent")
def runtime_audits_recent(
    limit: int = 20,
    session: Session = Depends(db_session_dependency),
) -> list[dict[str, object]]:
    return [
        audit_record_to_dict(record)
        for record in list_recent_trading_issue_reports(session, limit=limit)
    ]


@router.post("/runtime/audits/run")
async def runtime_audits_run(
    lookback_hours: int | None = None,
    deep: bool = False,
    manager: RuntimeTaskManager = Depends(runtime_manager),
) -> dict[str, object]:
    return await manager.run_system_audit(
        report_type=AuditReportType.INCIDENT_AUDIT,
        lookback_hours=lookback_hours,
        deep=deep,
    )


@router.get("/runtime/data-quality/latest")
def runtime_data_quality_latest(
    manager: RuntimeTaskManager = Depends(runtime_manager),
) -> dict[str, object]:
    return manager.latest_data_quality()


@router.post("/runtime/data-quality/check")
async def runtime_data_quality_check(
    manager: RuntimeTaskManager = Depends(runtime_manager),
) -> dict[str, object]:
    return await manager.run_data_quality_check()


@router.get("/runtime/shadow/recent")
def runtime_shadow_recent(
    limit: int = 50,
    manager: RuntimeTaskManager = Depends(runtime_manager),
) -> list[dict[str, object]]:
    return manager.shadow_recent(limit)


@router.get("/runtime/shadow/open")
def runtime_shadow_open(
    limit: int = 50,
    manager: RuntimeTaskManager = Depends(runtime_manager),
) -> list[dict[str, object]]:
    return manager.shadow_open(limit)


@router.get("/runtime/shadow/report")
def runtime_shadow_report(
    hours: int = 24,
    manager: RuntimeTaskManager = Depends(runtime_manager),
) -> dict[str, object]:
    return manager.shadow_report(hours)


@router.post("/runtime/shadow/evaluate")
async def runtime_shadow_evaluate(
    manager: RuntimeTaskManager = Depends(runtime_manager),
) -> dict[str, object]:
    return await manager.run_shadow_evaluation()


def _audit_row(row: PipelineAudit) -> dict[str, object]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "symbol": row.symbol,
        "started_at": row.started_at.isoformat(),
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "stage": row.stage,
        "status": row.status,
        "signal_id": row.signal_id,
        "ai_analysis_id": row.ai_analysis_id,
        "risk_decision_id": row.risk_decision_id,
        "order_record_id": row.order_record_id,
        "error_message": row.error_message,
        "raw_context_json": row.raw_context_json,
    }


def _network_readiness(report: dict[str, object] | None) -> dict[str, object]:
    if not report:
        return {
            "binance_testnet_rest": "UNKNOWN",
            "binance_testnet_ws": "UNKNOWN",
            "openai_api": "UNKNOWN",
            "proxy_env_present": False,
            "last_diagnostics_at": None,
        }
    environment = report["environment"]
    connectivity = report["connectivity"]
    return {
        "binance_testnet_rest": connectivity["binance_testnet_rest"]["status"],
        "binance_testnet_ws": connectivity["binance_testnet_ws"]["status"],
        "openai_api": connectivity["openai_api"]["status"],
        "proxy_env_present": any(value == "present" for value in environment["proxy_env"].values()),
        "last_diagnostics_at": report.get("created_at"),
    }


def _openai_usage_warnings(summary: dict[str, Any], settings: Settings) -> list[str]:
    warnings: list[str] = []
    estimated = float(summary.get("estimated_cost_usd", 0.0) or 0.0)
    if estimated >= settings.openai_daily_budget_usd * 0.8:
        warnings.append("Estimated selected-window usage is near the daily budget.")
    if estimated >= settings.openai_monthly_budget_usd * 0.8:
        warnings.append("Estimated selected-window usage is near the monthly budget.")
    status_counts = {
        status
        for bucket in [*summary.get("by_role", {}).values(), *summary.get("by_model", {}).values()]
        for status in ("failed", "skipped_budget")
        if bucket.get(status, 0)
    }
    if "failed" in status_counts:
        warnings.append("Recent OpenAI calls include failures.")
    if "skipped_budget" in status_counts:
        warnings.append("BudgetGuard skipped at least one OpenAI call.")
    return warnings
