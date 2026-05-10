from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from journal.models import PipelineAudit


class PipelineStage(StrEnum):
    KLINE_RECEIVED = "KLINE_RECEIVED"
    SNAPSHOT_CREATED = "SNAPSHOT_CREATED"
    SIGNAL_GENERATED = "SIGNAL_GENERATED"
    AI_REVIEWED = "AI_REVIEWED"
    RISK_CHECKED = "RISK_CHECKED"
    ORDER_CREATED = "ORDER_CREATED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    USER_STREAM_UPDATED = "USER_STREAM_UPDATED"
    RECONCILED = "RECONCILED"
    TRADE_REVIEWED = "TRADE_REVIEWED"
    FAILED = "FAILED"


class PipelineStatus(StrEnum):
    OK = "OK"
    REJECTED = "REJECTED"
    WARNING = "WARNING"
    ERROR = "ERROR"


def record_pipeline_stage(
    session: Session,
    *,
    run_id: str,
    symbol: str,
    stage: PipelineStage | str,
    status: PipelineStatus | str,
    raw_context_json: dict[str, Any] | None = None,
    signal_id: int | None = None,
    ai_analysis_id: int | None = None,
    risk_decision_id: int | None = None,
    order_record_id: int | None = None,
    error_message: str | None = None,
) -> PipelineAudit:
    now = datetime.now(UTC)
    record = PipelineAudit(
        run_id=run_id,
        symbol=symbol.upper(),
        started_at=now,
        completed_at=now,
        stage=str(stage.value if isinstance(stage, StrEnum) else stage),
        status=str(status.value if isinstance(status, StrEnum) else status),
        signal_id=signal_id,
        ai_analysis_id=ai_analysis_id,
        risk_decision_id=risk_decision_id,
        order_record_id=order_record_id,
        error_message=error_message,
        raw_context_json=raw_context_json or {},
    )
    session.add(record)
    session.flush()
    return record


def recent_pipeline_audits(session: Session, limit: int = 50) -> list[PipelineAudit]:
    return session.scalars(
        select(PipelineAudit).order_by(desc(PipelineAudit.started_at)).limit(limit)
    ).all()


def pipeline_audits_by_run_id(session: Session, run_id: str) -> list[PipelineAudit]:
    return session.scalars(
        select(PipelineAudit)
        .where(PipelineAudit.run_id == run_id)
        .order_by(PipelineAudit.started_at)
    ).all()

