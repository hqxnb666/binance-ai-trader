from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
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
    AIAnalysis,
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
from journal.strategy_plan_store import (
    get_active_strategy_plan,
    list_recent_strategy_plans,
    sanitize_json,
)
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
            "strategy_name": row.strategy_name,
            "strategy_version": row.strategy_version,
            "timeframe": row.timeframe,
            "side": row.side,
            "signal_type": row.signal_type,
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


@router.get("/runtime/strategy-plan/latest")
def runtime_strategy_plan_latest(
    session: Session = Depends(db_session_dependency),
) -> dict[str, object]:
    plan = get_active_strategy_plan(session)
    if plan is None:
        return {"status": "NO_ACTIVE_STRATEGY_PLAN", "plan": None}
    return {"status": "OK", "plan": _strategy_plan_to_dict(plan)}


@router.get("/runtime/strategy-plan/recent")
def runtime_strategy_plan_recent(
    limit: int = Query(default=10, ge=1, le=50),
    session: Session = Depends(db_session_dependency),
) -> dict[str, object]:
    return {
        "status": "OK",
        "items": [
            _strategy_plan_to_dict(plan)
            for plan in list_recent_strategy_plans(session, limit=limit)
        ],
    }


@router.get("/runtime/diagnostic-snapshot")
def runtime_diagnostic_snapshot(
    request: Request,
    shadow_limit: int = Query(default=100, ge=1, le=300),
    signal_limit: int = Query(default=50, ge=1, le=200),
    plan_limit: int = Query(default=10, ge=1, le=50),
    manager: RuntimeTaskManager = Depends(runtime_manager),
    session: Session = Depends(db_session_dependency),
    settings: Settings = Depends(settings_dependency),
) -> dict[str, object]:
    errors: list[dict[str, object]] = []

    runtime_health_payload = _safe_section(
        "runtime_health",
        lambda: {
            **manager.health(),
            "network_readiness": _network_readiness(getattr(manager, "latest_diagnostics", None)),
        },
        errors,
    )
    safe_config_payload = _safe_section("safe_config", settings.safe_config, errors)
    status_payload = _safe_section(
        "status",
        lambda: _status_payload(settings=settings, session=session),
        errors,
    )
    strategy_config_payload = _safe_section("strategy_config", strategy_config_response, errors)
    risk_config_payload = _safe_section(
        "risk_config",
        lambda: {"config": load_risk_config(), "read_only": True},
        errors,
    )
    active_plan_payload = _safe_section(
        "active_strategy_plan",
        lambda: _active_strategy_plan_payload(session),
        errors,
    )
    recent_plans_payload = _safe_section(
        "recent_strategy_plans",
        lambda: [
            _strategy_plan_to_dict(plan)
            for plan in list_recent_strategy_plans(session, plan_limit)
        ],
        errors,
    )
    last_snapshots_payload = _safe_section("last_snapshots", manager.last_snapshots, errors)
    recent_signals_payload = _safe_section(
        "recent_signals",
        lambda: _recent_signals_payload(session, signal_limit),
        errors,
    )
    ai_reviews_payload = _safe_section(
        "last_ai_reviews",
        lambda: manager.last_ai_reviews() or _recent_ai_reviews_payload(session, signal_limit),
        errors,
    )
    risk_decisions_payload = _safe_section(
        "last_risk_decisions",
        lambda: manager.last_risk_decisions()
        or _recent_risk_decisions_payload(session, signal_limit),
        errors,
    )
    data_quality_payload = _safe_section("data_quality", manager.latest_data_quality, errors)
    shadow_report_payload = _safe_section("shadow_report", manager.shadow_report, errors)
    shadow_recent_payload = _safe_section(
        "shadow_recent", lambda: manager.shadow_recent(shadow_limit), errors
    )
    shadow_open_payload = _safe_section(
        "shadow_open", lambda: manager.shadow_open(shadow_limit), errors
    )
    readiness_payload = _safe_section(
        "readiness_latest",
        lambda: getattr(request.app.state, "latest_readiness_report", None)
        or {"status": "NO_READINESS_CHECK_RUN"},
        errors,
    )
    openai_usage_payload = _safe_section(
        "openai_usage_1d",
        lambda: _openai_usage_payload(session=session, settings=settings, days=1),
        errors,
    )
    audit_payload = _safe_section(
        "audit_latest",
        lambda: (
            audit_record_to_dict(get_latest_trading_issue_report(session))
            if get_latest_trading_issue_report(session)
            else {"status": "NO_AUDIT_REPORT"}
        ),
        errors,
    )
    blocking_attribution = _blocking_attribution(
        shadow_recent=shadow_recent_payload if isinstance(shadow_recent_payload, list) else [],
        risk_decisions=risk_decisions_payload if isinstance(risk_decisions_payload, list) else [],
        ai_reviews=ai_reviews_payload if isinstance(ai_reviews_payload, list) else [],
    )

    snapshot = {
        "schema_version": "diagnostic_snapshot_v1",
        "created_at": datetime.now(UTC).isoformat(),
        "purpose": "GPT strategy/risk/shadow review package",
        "safety_note": (
            "Read-only diagnostic snapshot. No order placement, no config mutation, no secrets."
        ),
        "runtime_health": runtime_health_payload,
        "safe_config": safe_config_payload,
        "status": status_payload,
        "strategy_config": strategy_config_payload,
        "risk_config": risk_config_payload,
        "active_strategy_plan": active_plan_payload,
        "recent_strategy_plans": recent_plans_payload,
        "last_snapshots": last_snapshots_payload,
        "recent_signals": recent_signals_payload,
        "last_ai_reviews": ai_reviews_payload,
        "last_risk_decisions": risk_decisions_payload,
        "data_quality": data_quality_payload,
        "shadow_report": shadow_report_payload,
        "shadow_recent": shadow_recent_payload,
        "shadow_open": shadow_open_payload,
        "readiness_latest": readiness_payload,
        "openai_usage_1d": openai_usage_payload,
        "audit_latest": audit_payload,
        "blocking_attribution": blocking_attribution,
        "diagnostic_summary": _diagnostic_summary(
            active_strategy_plan=active_plan_payload,
            data_quality=data_quality_payload,
            readiness=readiness_payload,
            blocking_attribution=blocking_attribution,
            errors=errors,
            counts={
                "recent_strategy_plans": len(recent_plans_payload)
                if isinstance(recent_plans_payload, list)
                else 0,
                "recent_signals": len(recent_signals_payload)
                if isinstance(recent_signals_payload, list)
                else 0,
                "shadow_recent": len(shadow_recent_payload)
                if isinstance(shadow_recent_payload, list)
                else 0,
                "shadow_open": len(shadow_open_payload)
                if isinstance(shadow_open_payload, list)
                else 0,
                "last_ai_reviews": len(ai_reviews_payload)
                if isinstance(ai_reviews_payload, list)
                else 0,
                "last_risk_decisions": len(risk_decisions_payload)
                if isinstance(risk_decisions_payload, list)
                else 0,
            },
        ),
        "diagnostics": {"errors": errors},
    }
    return sanitize_json(snapshot)


@router.get("/runtime/dashboard-summary")
def runtime_dashboard_summary(
    request: Request,
    manager: RuntimeTaskManager = Depends(runtime_manager),
    session: Session = Depends(db_session_dependency),
    settings: Settings = Depends(settings_dependency),
) -> dict[str, object]:
    snapshot = runtime_diagnostic_snapshot(
        request=request,
        shadow_limit=100,
        signal_limit=50,
        plan_limit=10,
        manager=manager,
        session=session,
        settings=settings,
    )
    return _dashboard_summary_from_snapshot(snapshot)


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


def _safe_section(
    name: str,
    loader: Any,
    errors: list[dict[str, object]],
) -> Any:
    try:
        return sanitize_json(loader())
    except Exception as exc:  # noqa: BLE001 - diagnostic snapshot should be fail-soft
        errors.append({"section": name, "error": str(exc)[:500]})
        return {"status": "NOT_AVAILABLE", "reason": str(exc)[:500]}


def _status_payload(*, settings: Settings, session: Session) -> dict[str, object]:
    return {
        "app_env": settings.app_env,
        "trading_mode": settings.trading_mode,
        "live_trading_enabled": settings.live_trading_enabled and settings.live_trading.enabled,
        "kill_switch_enabled": CircuitBreaker(session).is_enabled(),
        "symbols": settings.symbols.enabled_symbols,
    }


def _strategy_plan_to_dict(plan: Any) -> dict[str, object]:
    raw_output = sanitize_json(plan.raw_output_json or {})
    return {
        "id": plan.id,
        "status": plan.status,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
        "expires_at": plan.expires_at.isoformat() if plan.expires_at else None,
        "planning_mode": plan.planning_mode,
        "plan_action": plan.plan_action,
        "model": plan.model,
        "schema_version": plan.schema_version,
        "market_regime": plan.market_regime,
        "risk_mode": plan.risk_mode,
        "trade_bias": plan.trade_bias,
        "requires_human_review": plan.requires_human_review,
        "allowed_actions": plan.allowed_actions_json,
        "blocked_actions": plan.blocked_actions_json,
        "symbol_permissions": plan.symbol_permissions_json,
        "symbol_scope": plan.symbol_scope_json,
        "max_position_pct": float(plan.max_position_pct)
        if plan.max_position_pct is not None
        else None,
        "confidence": float(plan.confidence),
        "confidence_threshold": raw_output.get("confidence_threshold"),
        "reason_codes": plan.reason_codes_json,
        "summary": plan.explanation,
        "explanation": plan.explanation,
        "raw_output_json": raw_output,
        "output_hash": plan.output_hash,
    }


def _active_strategy_plan_payload(session: Session) -> dict[str, object]:
    plan = get_active_strategy_plan(session)
    if plan is None:
        return {"status": "NO_ACTIVE_STRATEGY_PLAN", "plan": None}
    return {"status": "OK", "plan": _strategy_plan_to_dict(plan)}


def _recent_signals_payload(session: Session, limit: int) -> list[dict[str, object]]:
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
            "strategy_name": row.strategy_name,
            "strategy_version": row.strategy_version,
            "timeframe": row.timeframe,
            "signal_type": row.signal_type,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


def _recent_ai_reviews_payload(session: Session, limit: int) -> list[dict[str, object]]:
    rows = session.scalars(
        select(AIAnalysis).order_by(desc(AIAnalysis.created_at)).limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "symbol": row.symbol,
            "analysis_type": row.analysis_type,
            "model": row.model,
            "schema_valid": row.schema_valid,
            "decision": row.decision,
            "confidence": float(row.confidence) if row.confidence is not None else None,
            "risk_level": row.risk_level,
            "created_at": row.created_at.isoformat(),
            "output_json": sanitize_json(row.output_json),
        }
        for row in rows
    ]


def _recent_risk_decisions_payload(session: Session, limit: int) -> list[dict[str, object]]:
    rows = session.scalars(
        select(RiskDecision).order_by(desc(RiskDecision.created_at)).limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "symbol": row.symbol,
            "signal_id": row.signal_id,
            "ai_analysis_id": row.ai_analysis_id,
            "approved": row.approved,
            "reason": row.reason,
            "risk_state_json": sanitize_json(row.risk_state_json),
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


def _openai_usage_payload(*, session: Session, settings: Settings, days: int) -> dict[str, object]:
    summary = summarize_openai_usage(session, days=days)
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "days": days,
        "summary": summary,
        "daily_budget_usd": settings.openai_daily_budget_usd,
        "monthly_budget_usd": settings.openai_monthly_budget_usd,
        "warnings": _openai_usage_warnings(summary, settings),
        "safety_note": "No raw prompts, raw responses, API keys, or request headers are returned.",
    }


def _blocking_attribution(
    *,
    shadow_recent: list[dict[str, object]],
    risk_decisions: list[dict[str, object]],
    ai_reviews: list[dict[str, object]],
) -> dict[str, int]:
    counts = {
        "strategy_no_trade": 0,
        "strategy_plan_blocked": 0,
        "ai_human_review": 0,
        "ai_rejected": 0,
        "risk_symbol_position_limit": 0,
        "risk_total_position_limit": 0,
        "data_quality_blocked": 0,
        "would_place_order": 0,
        "unknown": 0,
    }
    for row in shadow_recent:
        decision_type = str(row.get("decision_type", "")).upper()
        text = " ".join(
            [
                str(row.get("reason", "")),
                " ".join(str(item) for item in row.get("reason_codes", []) or []),
            ]
        ).lower()
        if decision_type == "WOULD_PLACE_ORDER":
            counts["would_place_order"] += 1
        elif decision_type == "DATA_QUALITY_BLOCKED":
            counts["data_quality_blocked"] += 1
        elif "strategy_no_trade" in text or "no_trade" in text:
            counts["strategy_no_trade"] += 1
        elif "active strategyplan" in text or "strategy plan" in text:
            counts["strategy_plan_blocked"] += 1
        elif "human review" in text or "human_review" in text:
            counts["ai_human_review"] += 1
        elif "ai rejected" in text or "reject_signal" in text:
            counts["ai_rejected"] += 1
        elif "symbol position limit" in text:
            counts["risk_symbol_position_limit"] += 1
        elif "total position limit" in text:
            counts["risk_total_position_limit"] += 1
        else:
            counts["unknown"] += 1
    for row in risk_decisions:
        reason = str(row.get("reason", "")).lower()
        if "symbol position limit" in reason:
            counts["risk_symbol_position_limit"] += 1
        elif "total position limit" in reason:
            counts["risk_total_position_limit"] += 1
    for row in ai_reviews:
        output_json = row.get("output_json")
        output_json = output_json if isinstance(output_json, dict) else {}
        decision = str(row.get("decision") or output_json.get("decision", "")).upper()
        if "HUMAN_REVIEW" in decision:
            counts["ai_human_review"] += 1
        elif "REJECT" in decision:
            counts["ai_rejected"] += 1
    return counts


def _diagnostic_summary(
    *,
    active_strategy_plan: Any,
    data_quality: Any,
    readiness: Any,
    blocking_attribution: dict[str, int],
    errors: list[dict[str, object]],
    counts: dict[str, int],
) -> dict[str, object]:
    primary_blockers: list[str] = []
    notes: list[str] = []
    if isinstance(data_quality, dict) and data_quality.get("overall_status") in {
        "CRITICAL",
        "DEGRADED",
    }:
        primary_blockers.append(f"DATA_QUALITY_{data_quality.get('overall_status')}")
    if isinstance(readiness, dict):
        for blocker in readiness.get("blockers", []) or []:
            primary_blockers.append(str(blocker))
    if isinstance(active_strategy_plan, dict):
        plan = active_strategy_plan.get("plan") or {}
        if plan and plan.get("risk_mode") == "no_trade":
            primary_blockers.append("ACTIVE_STRATEGY_PLAN_NO_TRADE")
        if plan and plan.get("requires_human_review"):
            primary_blockers.append("ACTIVE_STRATEGY_PLAN_REQUIRES_HUMAN_REVIEW")
    if blocking_attribution.get("would_place_order", 0) == 0:
        notes.append("No WOULD_PLACE_ORDER decisions in the selected shadow sample.")
    if errors:
        notes.append(
            "One or more diagnostic sections were unavailable; inspect diagnostics.errors."
        )
    return {
        "primary_blockers": sorted(set(primary_blockers)),
        "counts": counts,
        "notes": notes,
    }


def _dashboard_summary_from_snapshot(snapshot: dict[str, Any]) -> dict[str, object]:
    runtime_health = _dict_or_empty(snapshot.get("runtime_health"))
    status = _dict_or_empty(snapshot.get("status"))
    safe_config = _dict_or_empty(snapshot.get("safe_config"))
    data_quality = _dict_or_empty(snapshot.get("data_quality"))
    shadow_report = _dict_or_empty(snapshot.get("shadow_report"))
    active_plan_payload = _dict_or_empty(snapshot.get("active_strategy_plan"))
    active_plan = _dict_or_empty(active_plan_payload.get("plan"))
    recent_plans = _list_or_empty(snapshot.get("recent_strategy_plans"))
    recent_signals = _list_or_empty(snapshot.get("recent_signals"))
    ai_reviews = _list_or_empty(snapshot.get("last_ai_reviews"))
    risk_decisions = _list_or_empty(snapshot.get("last_risk_decisions"))
    audit_latest = _dict_or_empty(snapshot.get("audit_latest"))
    risk_config = _dict_or_empty(snapshot.get("risk_config")).get("config", {})
    strategy_config = _dict_or_empty(snapshot.get("strategy_config")).get("config", {})
    blocking = _dict_or_empty(snapshot.get("blocking_attribution"))

    plan_status_counts = _count_values(recent_plans, "status")
    plan_reason_text = " ".join(
        " ".join(str(code) for code in plan.get("reason_codes", []) or [])
        for plan in recent_plans
        if isinstance(plan, dict)
    )
    signal_counts: dict[str, int] = {}
    for signal in recent_signals:
        if not isinstance(signal, dict):
            continue
        key = f"{signal.get('symbol', 'UNKNOWN')}_{signal.get('side', 'UNKNOWN')}"
        signal_counts[key] = signal_counts.get(key, 0) + 1

    ai_counts = _ai_decision_counts(ai_reviews)
    risk_reason_counts = _count_values(risk_decisions, "reason")
    rejected_count = sum(1 for row in risk_decisions if not _dict_or_empty(row).get("approved"))
    approved_count = sum(1 for row in risk_decisions if _dict_or_empty(row).get("approved"))
    missing = _missing_sections(snapshot)
    human_summary = _human_dashboard_summary(
        runtime_health=runtime_health,
        data_quality=data_quality,
        active_plan_payload=active_plan_payload,
        shadow_report=shadow_report,
        blocking=blocking,
        missing=missing,
    )

    return sanitize_json(
        {
            "schema_version": "dashboard_summary_v1",
            "created_at": datetime.now(UTC).isoformat(),
            "safety": {
                "runtime_state": runtime_health.get("state", "UNKNOWN"),
                "trading_mode": runtime_health.get(
                    "trading_mode", status.get("trading_mode", "UNKNOWN")
                ),
                "dry_run": runtime_health.get(
                    "dry_run", safe_config.get("trading_dry_run", True)
                ),
                "order_execution_enabled": runtime_health.get(
                    "order_execution_enabled",
                    safe_config.get("order_execution_enabled", False),
                ),
                "live_trading_enabled": status.get(
                    "live_trading_enabled",
                    safe_config.get("live_trading_enabled", False),
                ),
                "kill_switch_enabled": runtime_health.get(
                    "kill_switch_state", {}
                ).get("effective_enabled", status.get("kill_switch_enabled", False)),
                "market_stream_connected": runtime_health.get(
                    "market_stream_connected", False
                ),
                "user_stream_connected": runtime_health.get("user_stream_connected", False),
                "data_quality": data_quality.get("overall_status", data_quality.get("status")),
                "safe_for_order": data_quality.get("safe_for_order", False),
            },
            "diagnosis": {
                "primary_status": _primary_status(runtime_health, data_quality, audit_latest),
                "primary_blockers": snapshot.get("diagnostic_summary", {}).get(
                    "primary_blockers", []
                ),
                "human_summary": human_summary,
                "missing_sections": missing,
            },
            "shadow": {
                "total_decisions": shadow_report.get("total_decisions", 0),
                "would_place_order_count": shadow_report.get("would_place_order_count", 0),
                "risk_rejected_count": shadow_report.get("risk_rejected_count", 0),
                "ai_rejected_count": shadow_report.get("ai_rejected_count", 0),
                "data_quality_blocked_count": shadow_report.get(
                    "data_quality_blocked_count", 0
                ),
                "simulated_total_pnl_usdt": shadow_report.get(
                    "simulated_total_pnl_usdt", "0"
                ),
                "simulated_win_rate": shadow_report.get("simulated_win_rate"),
                "top_rejection_reasons": (
                    shadow_report.get("top_rejection_reasons", []) or []
                )[:5],
            },
            "strategy_plan": {
                "active_status": active_plan_payload.get("status", "UNKNOWN"),
                "risk_mode": active_plan.get("risk_mode"),
                "trade_bias": active_plan.get("trade_bias"),
                "requires_human_review": active_plan.get("requires_human_review"),
                "failed_count": plan_status_counts.get("FAILED", 0),
                "active_count": plan_status_counts.get("ACTIVE", 0),
                "superseded_count": plan_status_counts.get("SUPERSEDED", 0),
                "schema_invalid_count": plan_reason_text.count("STRATEGY_SCHEMA_INVALID"),
                "recent_compact": [_compact_plan(plan) for plan in recent_plans[:5]],
            },
            "signals": {
                "total": len(recent_signals),
                "by_symbol_side": signal_counts,
                "latest_signal_at": recent_signals[0].get("created_at")
                if recent_signals and isinstance(recent_signals[0], dict)
                else None,
            },
            "ai_reviews": {
                "approve_count": ai_counts.get("APPROVE_TO_RISK_ENGINE", 0),
                "human_review_count": ai_counts.get("HUMAN_REVIEW_REQUIRED", 0),
                "reject_count": ai_counts.get("REJECT_SIGNAL", 0),
                "decision_counts": ai_counts,
            },
            "risk": {
                "approved_count": approved_count,
                "rejected_count": rejected_count,
                "top_reasons": _top_counts(risk_reason_counts),
            },
            "config": {
                "strategy": _compact_strategy_config(_dict_or_empty(strategy_config)),
                "risk": _compact_risk_config(_dict_or_empty(risk_config)),
            },
            "audit": {
                "overall_status": audit_latest.get("overall_status", audit_latest.get("status")),
                "highest_severity": audit_latest.get("highest_severity"),
                "issue_count": audit_latest.get("issue_count", 0),
                "summary": audit_latest.get("summary"),
                "top_issues": _audit_top_issues(audit_latest),
            },
            "blocking_attribution": blocking,
        }
    )


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _count_values(rows: list[Any], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = str(row.get(key, "UNKNOWN"))
        counts[value] = counts.get(value, 0) + 1
    return counts


def _top_counts(counts: dict[str, int], limit: int = 5) -> list[dict[str, object]]:
    return [
        {"reason": reason, "count": count}
        for reason, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]


def _ai_decision_counts(rows: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        output = _dict_or_empty(row.get("output_json"))
        decision = str(row.get("decision") or output.get("decision") or "UNKNOWN")
        counts[decision] = counts.get(decision, 0) + 1
    return counts


def _compact_plan(plan: Any) -> dict[str, object]:
    plan = _dict_or_empty(plan)
    return {
        "id": plan.get("id"),
        "status": plan.get("status"),
        "risk_mode": plan.get("risk_mode"),
        "trade_bias": plan.get("trade_bias"),
        "reason_codes": (plan.get("reason_codes", []) or [])[:2],
        "expires_at": plan.get("expires_at"),
    }


def _compact_strategy_config(config: dict[str, Any]) -> dict[str, object]:
    ema = _dict_or_empty(config.get("ema_trend"))
    return {
        "ema_fast": ema.get("ema_fast"),
        "ema_slow": ema.get("ema_slow"),
        "rsi_min": ema.get("rsi_min"),
        "rsi_max": ema.get("rsi_max"),
        "volume_ratio_min": ema.get("volume_ratio_min"),
    }


def _compact_risk_config(config: dict[str, Any]) -> dict[str, object]:
    risk = _dict_or_empty(config.get("risk"))
    return {
        "max_position_pct_per_symbol": risk.get("max_position_pct_per_symbol"),
        "max_total_position_pct": risk.get("max_total_position_pct"),
        "allow_limit_orders": risk.get("allow_limit_orders"),
        "allow_market_orders": risk.get("allow_market_orders"),
        "kill_switch_enabled": risk.get("kill_switch_enabled"),
    }


def _audit_top_issues(audit: dict[str, Any]) -> list[dict[str, object]]:
    report = _dict_or_empty(audit.get("report"))
    issues = _list_or_empty(report.get("issues"))
    return [
        {
            "severity": issue.get("severity"),
            "category": issue.get("category"),
            "title": issue.get("title"),
        }
        for issue in issues[:3]
        if isinstance(issue, dict)
    ]


def _missing_sections(snapshot: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key, value in snapshot.items():
        if isinstance(value, dict) and value.get("status") in {
            "NOT_AVAILABLE",
            "NO_ACTIVE_STRATEGY_PLAN",
            "NO_READINESS_CHECK_RUN",
            "NO_AUDIT_REPORT",
            "NO_DATA_QUALITY_SNAPSHOT",
        }:
            missing.append(key)
    if not _dict_or_empty(snapshot.get("last_snapshots")):
        missing.append("last_snapshots")
    return sorted(set(missing))


def _primary_status(
    runtime_health: dict[str, Any],
    data_quality: dict[str, Any],
    audit: dict[str, Any],
) -> str:
    if runtime_health.get("last_error") or data_quality.get("overall_status") == "CRITICAL":
        return "ERROR"
    if data_quality.get("overall_status") in {"DEGRADED", "WARNING"}:
        return "WATCH"
    if audit.get("highest_severity") in {"HIGH", "CRITICAL"}:
        return "WATCH"
    return "OK"


def _human_dashboard_summary(
    *,
    runtime_health: dict[str, Any],
    data_quality: dict[str, Any],
    active_plan_payload: dict[str, Any],
    shadow_report: dict[str, Any],
    blocking: dict[str, Any],
    missing: list[str],
) -> list[str]:
    lines: list[str] = []
    if runtime_health.get("state") == "STOPPED":
        lines.append(
            "当前 Runtime 未运行。请先启动 Dry Run，再加载诊断包，"
            "否则行情快照、数据质量和 readiness 可能为空。"
        )
    if shadow_report.get("would_place_order_count", 0) == 0:
        lines.append(
            "当前没有 WOULD_PLACE_ORDER。优先检查 StrategyPlan、AI 审查和 "
            "RiskEngine 拒绝原因。"
        )
    top_block = max(blocking.items(), key=lambda item: item[1], default=(None, 0))
    if top_block[0] and top_block[1]:
        lines.append(f"当前主要阻断归因：{top_block[0]} = {top_block[1]}。")
    if active_plan_payload.get("status") == "NO_ACTIVE_STRATEGY_PLAN":
        lines.append(
            "当前没有有效 Active StrategyPlan；若信号存在但 WOULD_PLACE_ORDER 为 0，"
            "应先检查 plan 过期、schema invalid 或 no-trade 状态。"
        )
    if data_quality.get("status") == "NO_DATA_QUALITY_SNAPSHOT":
        lines.append("尚未运行 DataQuality 检查。请点击一键运行检查。")
    if "readiness_latest" in missing:
        lines.append("尚未运行 Readiness 检查；需要评估 Testnet 准备状态时请运行。")
    return lines[:5]
