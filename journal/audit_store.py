from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ai.audit_schemas import AuditSeverity, TradingIssueReport, highest_severity
from journal.models import TradingIssueReportRecord
from journal.strategy_plan_store import sanitize_json

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "audits"
SEVERITY_RANK = {
    "INFO": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


def save_trading_issue_report(
    session: Session,
    *,
    report: TradingIssueReport,
    raw_input_json: dict[str, Any],
    report_path: str | None = None,
) -> TradingIssueReportRecord:
    input_json = sanitize_json(raw_input_json)
    output_json = sanitize_json(report.model_dump(mode="json"))
    severity = highest_severity(report.issues)
    record = TradingIssueReportRecord(
        report_type=report.report_type.value,
        model=report.model,
        overall_status=report.overall_status,
        highest_severity=severity.value,
        issue_count=len(report.issues),
        time_window_start=report.time_window_start,
        time_window_end=report.time_window_end,
        input_hash=report.input_hash or _hash_json(input_json),
        output_hash=report.output_hash or _hash_json(output_json),
        raw_input_json_sanitized=input_json,
        raw_output_json_sanitized=output_json,
        summary=report.summary,
        report_path=report_path,
    )
    session.add(record)
    session.flush()
    return record


def get_latest_trading_issue_report(session: Session) -> TradingIssueReportRecord | None:
    return session.scalar(
        select(TradingIssueReportRecord).order_by(desc(TradingIssueReportRecord.created_at))
    )


def list_recent_trading_issue_reports(
    session: Session,
    limit: int = 20,
) -> list[TradingIssueReportRecord]:
    return session.scalars(
        select(TradingIssueReportRecord)
        .order_by(desc(TradingIssueReportRecord.created_at))
        .limit(limit)
    ).all()


def get_highest_recent_audit_severity(
    session: Session,
    *,
    lookback_hours: int = 24,
) -> str:
    since = datetime.now(UTC) - timedelta(hours=lookback_hours)
    rows = session.scalars(
        select(TradingIssueReportRecord).where(TradingIssueReportRecord.created_at >= since)
    ).all()
    if not rows:
        return AuditSeverity.INFO.value
    return max(rows, key=lambda row: SEVERITY_RANK.get(row.highest_severity, 0)).highest_severity


def save_audit_report_file(report: TradingIssueReport) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"audit-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return path


def audit_record_to_dict(record: TradingIssueReportRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "created_at": record.created_at.isoformat(),
        "report_type": record.report_type,
        "model": record.model,
        "overall_status": record.overall_status,
        "highest_severity": record.highest_severity,
        "issue_count": record.issue_count,
        "time_window_start": record.time_window_start.isoformat(),
        "time_window_end": record.time_window_end.isoformat(),
        "summary": record.summary,
        "report_path": record.report_path,
        "report": record.raw_output_json_sanitized,
    }


def _hash_json(payload: dict[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()
