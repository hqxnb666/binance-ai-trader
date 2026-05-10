from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ai.audit_schemas import TradingIssueReport
from journal.audit_store import (
    get_highest_recent_audit_severity,
    get_latest_trading_issue_report,
    list_recent_trading_issue_reports,
    save_trading_issue_report,
)
from journal.models import Base


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)()


def _report(severity: str = "LOW") -> TradingIssueReport:
    now = datetime.now(UTC)
    return TradingIssueReport.model_validate(
        {
            "schema_version": "trading_issue_report_v1",
            "report_type": "PERIODIC_AUDIT",
            "created_at": now,
            "time_window_start": now - timedelta(hours=1),
            "time_window_end": now,
            "overall_status": "WATCH" if severity != "CRITICAL" else "CRITICAL",
            "summary": "audit summary",
            "issues": [
                {
                    "severity": severity,
                    "category": "RUNTIME",
                    "title": "test",
                    "evidence": ["evidence"],
                    "suspected_root_cause": "test",
                    "recommended_human_action": "Human review required.",
                    "requires_codex_change": False,
                    "auto_fix_allowed": False,
                    "can_modify_config": False,
                    "can_modify_strategy": False,
                    "can_place_order": False,
                    "related_ids": [],
                    "confidence": 0.7,
                }
            ],
            "recommended_next_human_steps": ["review"],
            "do_not_auto_modify": True,
            "model": "gpt-5.4-mini",
            "input_hash": None,
            "output_hash": None,
        }
    )


def test_audit_store_save_latest_list_and_sanitize() -> None:
    session = _session()
    record = save_trading_issue_report(
        session,
        report=_report(),
        raw_input_json={"OPENAI_API_KEY": "sk-secret"},
    )
    assert record.id is not None
    assert get_latest_trading_issue_report(session).id == record.id
    assert len(list_recent_trading_issue_reports(session)) == 1
    assert "sk-secret" not in str(record.raw_input_json_sanitized)
    assert get_highest_recent_audit_severity(session) == "LOW"
