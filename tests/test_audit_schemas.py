from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from ai.audit_schemas import AuditIssue, TradingIssueReport


def _issue(**overrides: Any) -> dict[str, Any]:
    payload = {
        "severity": "LOW",
        "category": "RUNTIME",
        "title": "Runtime looks normal",
        "evidence": ["health state RUNNING"],
        "suspected_root_cause": "No issue",
        "recommended_human_action": "Human review can continue monitoring.",
        "requires_codex_change": False,
        "auto_fix_allowed": False,
        "can_modify_config": False,
        "can_modify_strategy": False,
        "can_place_order": False,
        "related_ids": [],
        "confidence": 0.7,
    }
    payload.update(overrides)
    return payload


def _report(**overrides: Any) -> dict[str, Any]:
    now = datetime.now(UTC)
    payload = {
        "schema_version": "trading_issue_report_v1",
        "report_type": "PERIODIC_AUDIT",
        "created_at": now,
        "time_window_start": now - timedelta(hours=6),
        "time_window_end": now,
        "overall_status": "WATCH",
        "summary": "No critical issue.",
        "issues": [_issue()],
        "recommended_next_human_steps": ["Continue monitoring."],
        "report_truncated": False,
        "do_not_auto_modify": True,
        "model": "gpt-5.4-mini",
        "input_hash": None,
        "output_hash": None,
    }
    payload.update(overrides)
    return payload


def test_trading_issue_report_valid_sample_passes() -> None:
    report = TradingIssueReport.model_validate(_report())
    assert report.do_not_auto_modify is True


def test_audit_issue_auto_fix_must_be_false() -> None:
    with pytest.raises(ValidationError):
        AuditIssue.model_validate(_issue(auto_fix_allowed=True))


def test_do_not_auto_modify_must_be_true() -> None:
    with pytest.raises(ValidationError):
        TradingIssueReport.model_validate(_report(do_not_auto_modify=False))


def test_critical_issue_cannot_report_ok() -> None:
    with pytest.raises(ValueError):
        TradingIssueReport.model_validate(
            _report(overall_status="OK", issues=[_issue(severity="CRITICAL")])
        )


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        TradingIssueReport.model_validate(_report(extra_field=True))


def test_audit_schema_required_properties_are_consistent() -> None:
    for schema in (AuditIssue.model_json_schema(), TradingIssueReport.model_json_schema()):
        _assert_strict(schema)


def _assert_strict(node: Any) -> None:
    if isinstance(node, dict):
        if node.get("type") == "object" or "properties" in node:
            properties = node.get("properties")
            assert isinstance(properties, dict)
            assert set(node.get("required", [])) <= set(properties)
            assert node.get("additionalProperties") is not True
        for value in node.values():
            _assert_strict(value)
    elif isinstance(node, list):
        for item in node:
            _assert_strict(item)
