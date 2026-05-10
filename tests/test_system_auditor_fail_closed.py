from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ai.audit_schemas import AuditCategory, AuditReportType
from ai.system_auditor import SystemAuditor
from config.settings import load_settings
from journal.models import Base, OpenAIUsageRecord
from journal.openai_usage_store import record_openai_usage


class RaisingClient:
    def parse(self, **kwargs):
        raise RuntimeError("boom")


class InvalidClient:
    def parse(self, **kwargs):
        return {"bad": "shape"}


class ShouldNotCallClient:
    def parse(self, **kwargs):
        raise AssertionError("auditor should be skipped by BudgetGuard")


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)()


def test_openai_error_generates_fallback_report() -> None:
    auditor = SystemAuditor(load_settings(), client=RaisingClient())
    result = auditor.audit(audit_context={}, report_type=AuditReportType.PERIODIC_AUDIT)
    assert result.schema_valid is False
    assert result.report.do_not_auto_modify is True
    assert result.report.issues[0].auto_fix_allowed is False
    assert result.report.issues[0].can_place_order is False


def test_schema_invalid_generates_fallback_report() -> None:
    auditor = SystemAuditor(load_settings(), client=InvalidClient())
    result = auditor.audit(audit_context={}, report_type=AuditReportType.PERIODIC_AUDIT)
    assert result.schema_valid is False
    assert result.report.issues[0].category == AuditCategory.OPENAI_SCHEMA


def test_budget_guard_block_skips_auditor(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_DAILY_BUDGET_USD", "0.001")
    settings = load_settings()
    session = _session()
    record_openai_usage(
        session,
        role="system_auditor",
        model="gpt-5.4-mini",
        operation_name="system_audit.periodic_audit",
        status="SUCCESS",
        estimated_cost_usd="0.002",
    )
    result = SystemAuditor(settings, client=ShouldNotCallClient()).audit(
        audit_context={},
        usage_session=session,
    )
    assert result.report.issues[0].category == AuditCategory.OPENAI_BUDGET
    assert result.report.issues[0].title == "System audit skipped by BudgetGuard"
    assert any(row.status == "SKIPPED_BUDGET" for row in session.query(OpenAIUsageRecord).all())
