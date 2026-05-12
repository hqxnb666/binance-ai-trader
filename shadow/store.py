from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from config.settings import BASE_DIR, Settings
from journal.models import ShadowDecisionRecord, ShadowEvaluationRecord
from journal.strategy_plan_store import sanitize_json
from shadow.attribution import (
    build_shadow_attribution_summary,
    primary_blocking_layer,
    shadow_attribution_human_summary,
)
from shadow.schemas import (
    ShadowDecision,
    ShadowDecisionStatus,
    ShadowDecisionType,
    ShadowEvaluation,
    ShadowRejectionReason,
    ShadowReport,
    ShadowTradeSummary,
)

OPEN_STATUSES = {ShadowDecisionStatus.CREATED.value, ShadowDecisionStatus.TRACKING.value}


def create_shadow_decision(session: Session, decision: ShadowDecision) -> ShadowDecisionRecord:
    payload = decision.model_dump(mode="json")
    record = ShadowDecisionRecord(
        shadow_id=decision.shadow_id,
        created_at=decision.created_at,
        updated_at=decision.created_at,
        status=decision.status.value,
        decision_type=decision.decision_type.value,
        symbol=decision.symbol.upper(),
        side=decision.side.upper(),
        strategy_plan_id=decision.strategy_plan_id,
        signal_review_id=decision.signal_review_id,
        risk_decision_id=decision.risk_decision_id,
        data_quality_snapshot_id=decision.data_quality_snapshot_id,
        order_would_be_submitted=decision.order_would_be_submitted,
        order_type=decision.order_type,
        simulated_entry_price=_decimal_or_none(decision.simulated_entry_price),
        simulated_quantity=_decimal_or_none(decision.simulated_quantity),
        simulated_notional=_decimal_or_none(decision.simulated_notional),
        reason=decision.reason[:1000],
        reason_codes_json=payload["reason_codes"][:20],
        context_summary_json=_sanitize_shadow_context(payload["context_summary"]),
        expires_at=decision.expires_at,
        dry_run=decision.dry_run,
        order_execution_enabled=decision.order_execution_enabled,
    )
    session.add(record)
    session.flush()
    return record


def get_shadow_decision(session: Session, shadow_id: str) -> ShadowDecisionRecord | None:
    return session.scalar(
        select(ShadowDecisionRecord).where(ShadowDecisionRecord.shadow_id == shadow_id)
    )


def list_open_shadow_decisions(
    session: Session,
    *,
    limit: int = 50,
    would_place_only: bool = False,
) -> list[ShadowDecisionRecord]:
    query = (
        select(ShadowDecisionRecord)
        .where(ShadowDecisionRecord.status.in_(OPEN_STATUSES))
        .order_by(desc(ShadowDecisionRecord.created_at))
        .limit(limit)
    )
    if would_place_only:
        query = query.where(
            ShadowDecisionRecord.decision_type == ShadowDecisionType.WOULD_PLACE_ORDER.value
        )
    return session.scalars(query).all()


def list_recent_shadow_decisions(
    session: Session,
    *,
    limit: int = 50,
) -> list[ShadowDecisionRecord]:
    return session.scalars(
        select(ShadowDecisionRecord)
        .order_by(desc(ShadowDecisionRecord.created_at))
        .limit(limit)
    ).all()


def add_shadow_evaluation(
    session: Session,
    evaluation: ShadowEvaluation,
) -> ShadowEvaluationRecord:
    record = ShadowEvaluationRecord(
        shadow_id=evaluation.shadow_id,
        evaluated_at=evaluation.evaluated_at,
        current_price=Decimal(evaluation.current_price),
        minutes_since_entry=evaluation.minutes_since_entry,
        unrealized_pnl_usdt=Decimal(evaluation.unrealized_pnl_usdt),
        unrealized_pnl_pct=evaluation.unrealized_pnl_pct,
        mfe_usdt=Decimal(evaluation.mfe_usdt),
        mae_usdt=Decimal(evaluation.mae_usdt),
        status=evaluation.status.value,
        exit_reason=evaluation.exit_reason.value if evaluation.exit_reason else None,
    )
    session.add(record)
    session.flush()
    return record


def close_shadow_decision(
    session: Session,
    shadow_id: str,
    *,
    status: ShadowDecisionStatus = ShadowDecisionStatus.CLOSED,
) -> ShadowDecisionRecord | None:
    record = get_shadow_decision(session, shadow_id)
    if record is None:
        return None
    record.status = status.value
    record.updated_at = datetime.now(UTC)
    session.flush()
    return record


def latest_evaluation_for_shadow(
    session: Session,
    shadow_id: str,
) -> ShadowEvaluationRecord | None:
    return session.scalar(
        select(ShadowEvaluationRecord)
        .where(ShadowEvaluationRecord.shadow_id == shadow_id)
        .order_by(desc(ShadowEvaluationRecord.evaluated_at))
    )


def build_shadow_report(
    session: Session,
    *,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    hours: int = 24,
) -> ShadowReport:
    end = window_end or datetime.now(UTC)
    start = window_start or end - timedelta(hours=hours)
    decisions = session.scalars(
        select(ShadowDecisionRecord)
        .where(ShadowDecisionRecord.created_at >= start)
        .where(ShadowDecisionRecord.created_at <= end)
        .order_by(ShadowDecisionRecord.created_at)
    ).all()
    latest_evals = _latest_evaluations(session, [record.shadow_id for record in decisions])
    pnl_values: list[Decimal] = []
    pnl_pcts: list[float] = []
    trade_summaries: list[ShadowTradeSummary] = []
    for record in decisions:
        if record.decision_type != ShadowDecisionType.WOULD_PLACE_ORDER.value:
            continue
        evaluation = latest_evals.get(record.shadow_id)
        if evaluation is None:
            continue
        pnl = Decimal(evaluation.unrealized_pnl_usdt)
        pnl_values.append(pnl)
        pnl_pcts.append(float(evaluation.unrealized_pnl_pct))
        trade_summaries.append(
            ShadowTradeSummary(
                shadow_id=record.shadow_id,
                symbol=record.symbol,
                side=record.side,
                simulated_pnl_usdt=_decimal_str(pnl),
                simulated_pnl_pct=float(evaluation.unrealized_pnl_pct),
            )
        )
    total_pnl = sum(pnl_values, Decimal("0"))
    wins = sum(1 for pnl in pnl_values if pnl > 0)
    rejected = [
        record
        for record in decisions
        if record.decision_type != ShadowDecisionType.WOULD_PLACE_ORDER.value
    ]
    top_reasons = _top_rejection_reasons(rejected)
    best = max(trade_summaries, key=lambda item: Decimal(item.simulated_pnl_usdt), default=None)
    worst = min(trade_summaries, key=lambda item: Decimal(item.simulated_pnl_usdt), default=None)
    closed_count = sum(
        1
        for record in decisions
        if record.status
        in {
            ShadowDecisionStatus.CLOSED.value,
            ShadowDecisionStatus.EXPIRED.value,
            ShadowDecisionStatus.INVALIDATED.value,
        }
    )
    attribution_summary = build_shadow_attribution_summary(
        session,
        window_start=start,
        window_end=end,
    )
    return ShadowReport(
        created_at=datetime.now(UTC),
        window_start=start,
        window_end=end,
        total_decisions=len(decisions),
        would_place_order_count=sum(
            1
            for record in decisions
            if record.decision_type == ShadowDecisionType.WOULD_PLACE_ORDER.value
        ),
        risk_rejected_count=sum(
            1
            for record in decisions
            if record.decision_type == ShadowDecisionType.RISK_REJECTED.value
        ),
        ai_rejected_count=sum(
            1
            for record in decisions
            if record.decision_type == ShadowDecisionType.AI_REJECTED.value
        ),
        data_quality_blocked_count=sum(
            1
            for record in decisions
            if record.decision_type == ShadowDecisionType.DATA_QUALITY_BLOCKED.value
        ),
        closed_shadow_trades=closed_count,
        simulated_win_rate=wins / len(pnl_values) if pnl_values else None,
        simulated_total_pnl_usdt=_decimal_str(total_pnl),
        simulated_avg_pnl_pct=sum(pnl_pcts) / len(pnl_pcts) if pnl_pcts else None,
        best_shadow_trade=best,
        worst_shadow_trade=worst,
        top_rejection_reasons=top_reasons,
        attribution_summary=attribution_summary,
        primary_blocking_layer=primary_blocking_layer(attribution_summary),
        human_summary=shadow_attribution_human_summary(attribution_summary),
        summary=(
            f"{len(decisions)} shadow decisions, "
            f"{len(pnl_values)} evaluated would-place decisions, "
            f"simulated PnL {total_pnl:.8f} USDT."
        ),
    )


def save_shadow_report(report: ShadowReport, settings: Settings) -> Path:
    path = shadow_report_dir(settings)
    path.mkdir(parents=True, exist_ok=True)
    report_path = path / f"shadow-report-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report_path


def shadow_report_dir(settings: Settings) -> Path:
    path = Path(settings.shadow_mode_report_dir)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def shadow_decision_to_dict(record: ShadowDecisionRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "shadow_id": record.shadow_id,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        "status": record.status,
        "decision_type": record.decision_type,
        "symbol": record.symbol,
        "side": record.side,
        "strategy_plan_id": record.strategy_plan_id,
        "signal_review_id": record.signal_review_id,
        "risk_decision_id": record.risk_decision_id,
        "data_quality_snapshot_id": record.data_quality_snapshot_id,
        "order_would_be_submitted": record.order_would_be_submitted,
        "order_type": record.order_type,
        "simulated_entry_price": _decimal_str(record.simulated_entry_price),
        "simulated_quantity": _decimal_str(record.simulated_quantity),
        "simulated_notional": _decimal_str(record.simulated_notional),
        "reason": record.reason,
        "reason_codes": record.reason_codes_json,
        "context_summary": _sanitize_shadow_context(record.context_summary_json),
        "expires_at": record.expires_at.isoformat(),
        "dry_run": record.dry_run,
        "order_execution_enabled": record.order_execution_enabled,
    }


def shadow_evaluation_to_dict(record: ShadowEvaluationRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "shadow_id": record.shadow_id,
        "evaluated_at": record.evaluated_at.isoformat(),
        "current_price": _decimal_str(record.current_price),
        "minutes_since_entry": float(record.minutes_since_entry),
        "unrealized_pnl_usdt": _decimal_str(record.unrealized_pnl_usdt),
        "unrealized_pnl_pct": float(record.unrealized_pnl_pct),
        "mfe_usdt": _decimal_str(record.mfe_usdt),
        "mae_usdt": _decimal_str(record.mae_usdt),
        "status": record.status,
        "exit_reason": record.exit_reason,
    }


def _latest_evaluations(
    session: Session,
    shadow_ids: list[str],
) -> dict[str, ShadowEvaluationRecord]:
    if not shadow_ids:
        return {}
    evaluations = session.scalars(
        select(ShadowEvaluationRecord)
        .where(ShadowEvaluationRecord.shadow_id.in_(shadow_ids))
        .order_by(ShadowEvaluationRecord.evaluated_at)
    ).all()
    latest: dict[str, ShadowEvaluationRecord] = {}
    for evaluation in evaluations:
        latest[evaluation.shadow_id] = evaluation
    return latest


def _top_rejection_reasons(records: list[ShadowDecisionRecord]) -> list[ShadowRejectionReason]:
    counter: Counter[str] = Counter()
    for record in records:
        codes = record.reason_codes_json or []
        if codes:
            for code in codes[:3]:
                counter[str(code)] += 1
        else:
            counter[record.reason[:80]] += 1
    return [
        ShadowRejectionReason(reason=reason, count=count)
        for reason, count in counter.most_common(10)
    ]


def _decimal_or_none(value: str | Decimal | None) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _decimal_str(value: Decimal | float | int | None) -> str:
    if value is None:
        return "0.000000000000"
    return format(Decimal(str(value)).quantize(Decimal("0.000000000001")), "f")


def _sanitize_shadow_context(value: Any) -> Any:
    sanitized = sanitize_json(value)
    return _scrub_sensitive_values(sanitized)


def _scrub_sensitive_values(value: Any) -> Any:
    markers = ("API_KEY", "SECRET", "TOKEN", "PASSWORD")
    if isinstance(value, dict):
        return {str(key): _scrub_sensitive_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub_sensitive_values(item) for item in value[:50]]
    if isinstance(value, str):
        upper = value.upper()
        if any(marker in upper for marker in markers):
            return "[REDACTED]"
    return value
