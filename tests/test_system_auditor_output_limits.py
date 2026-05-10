from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from ai.audit_schemas import AuditIssue, AuditReportType, TradingIssueReport
from ai.context_builder import build_audit_context
from ai.system_auditor import fallback_audit_report, normalize_trading_issue_report
from config.settings import load_settings


def _issue(index: int, *, text: str = "short") -> AuditIssue:
    return AuditIssue.model_validate(
        {
            "severity": "LOW",
            "category": "RUNTIME",
            "title": f"title {index} {text}",
            "evidence": [f"evidence {item} {text}" for item in range(10)],
            "suspected_root_cause": f"root cause {text}",
            "recommended_human_action": f"Human review required {text}",
            "requires_codex_change": False,
            "auto_fix_allowed": False,
            "can_modify_config": False,
            "can_modify_strategy": False,
            "can_place_order": False,
            "related_ids": [],
            "confidence": 0.7,
        }
    )


def _report(issue_count: int = 8, *, text: str = "short") -> TradingIssueReport:
    now = datetime.now(UTC)
    return TradingIssueReport.model_validate(
        {
            "schema_version": "trading_issue_report_v1",
            "report_type": "PERIODIC_AUDIT",
            "created_at": now,
            "time_window_start": now - timedelta(hours=6),
            "time_window_end": now,
            "overall_status": "WATCH",
            "summary": f"summary {text}",
            "issues": [_issue(index, text=text) for index in range(issue_count)],
            "recommended_next_human_steps": [
                f"Human review step {index} {text}" for index in range(8)
            ],
            "report_truncated": False,
            "do_not_auto_modify": True,
            "model": "gpt-5.4-mini",
            "input_hash": None,
            "output_hash": None,
        }
    )


def test_normalize_trading_issue_report_applies_output_limits(monkeypatch) -> None:
    monkeypatch.setenv("SYSTEM_AUDITOR_MAX_ISSUES", "3")
    monkeypatch.setenv("SYSTEM_AUDITOR_MAX_EVIDENCE_PER_ISSUE", "2")
    monkeypatch.setenv("SYSTEM_AUDITOR_MAX_TEXT_CHARS", "80")
    settings = load_settings()
    normalized = normalize_trading_issue_report(_report(text="x" * 500), settings)

    assert len(normalized.issues) == 3
    assert normalized.report_truncated is True
    assert normalized.do_not_auto_modify is True
    assert len(normalized.recommended_next_human_steps) == 3
    for issue in normalized.issues:
        assert issue.auto_fix_allowed is False
        assert issue.can_modify_config is False
        assert issue.can_modify_strategy is False
        assert issue.can_place_order is False
        assert len(issue.evidence) == 2
        assert len(issue.title) <= 80
        assert len(issue.suspected_root_cause) <= 80
        assert len(issue.recommended_human_action) <= 80


def test_fallback_report_is_compact_and_read_only() -> None:
    now = datetime.now(UTC)
    report = fallback_audit_report(
        report_type=AuditReportType.PERIODIC_AUDIT,
        model="gpt-5.4-mini",
        window_start=now - timedelta(hours=1),
        window_end=now,
        category="OPENAI_SCHEMA",
        severity="MEDIUM",
        title="fallback " + "x" * 500,
        reason="schema invalid " + "y" * 500,
        input_hash=None,
        max_text_chars=120,
    )
    assert report.report_truncated is True
    assert report.do_not_auto_modify is True
    assert len(report.summary) <= 120
    assert len(report.issues[0].evidence[0]) <= 120
    assert report.issues[0].auto_fix_allowed is False
    assert report.issues[0].can_place_order is False


def test_audit_context_excludes_raw_payloads_and_secrets() -> None:
    settings = load_settings()
    context = build_audit_context(
        settings=settings,
        runtime_health={"state": "RUNNING", "raw_response": "raw response should not appear"},
        budget_status={"status": "ok"},
        account_state={"status": "unknown", "OPENAI_API_KEY": "sk-secret"},
        data_quality_summary={"raw_prompt": "prompt should not appear"},
        diagnostics_summary={
            "binance_testnet_rest": {"status": "OK", "details": "safe enough"},
            "raw_response": "raw diagnostics should not appear",
            "BINANCE_SECRET": "secret-value",
        },
    )
    rendered = json.dumps(context)
    assert "sk-secret" not in rendered
    assert "secret-value" not in rendered
    assert "prompt should not appear" not in rendered
    assert "raw response should not appear" not in rendered
    assert "raw diagnostics should not appear" not in rendered
    assert context["diagnostics_summary"]["binance_testnet_rest"]["status"] == "OK"


def test_trading_issue_report_schema_is_openai_strict_compatible() -> None:
    _assert_openai_strict(TradingIssueReport.model_json_schema())


def _assert_openai_strict(node: Any) -> None:
    if isinstance(node, dict):
        if node.get("type") == "object" or "properties" in node:
            properties = node.get("properties")
            assert isinstance(properties, dict)
            assert set(node.get("required", [])) == set(properties)
            assert node.get("additionalProperties") is not True
        for value in node.values():
            _assert_openai_strict(value)
    elif isinstance(node, list):
        for item in node:
            _assert_openai_strict(item)
