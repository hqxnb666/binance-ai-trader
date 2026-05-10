from __future__ import annotations

import json

from ai.context_builder import build_audit_context
from config.settings import load_settings


def test_audit_context_sanitizes_secrets_and_marks_unknown() -> None:
    settings = load_settings()
    context = build_audit_context(
        settings=settings,
        runtime_health={"state": "RUNNING", "last_error": None},
        budget_status={"openai_today_cost_usd": 0},
        account_state={"status": "unknown", "BINANCE_SECRET": "secret-value"},
        position_state=None,
    )
    rendered = json.dumps(context)
    assert "secret-value" not in rendered
    assert context["position_state"]["status"] == "unknown"
    assert context["security_guardrails"]["dry_run"] is True
    assert context["security_guardrails"]["order_execution_enabled"] is False
    assert context["security_guardrails"]["live_trading_enabled"] is False


def test_audit_context_truncates_when_too_large(monkeypatch) -> None:
    monkeypatch.setenv("AI_CONTEXT_MAX_JSON_CHARS", "1000")
    settings = load_settings()
    context = build_audit_context(
        settings=settings,
        runtime_health={"state": "RUNNING"},
        budget_status={"status": "ok"},
        recent_signal_reviews=[{"blob": "x" * 10000} for _ in range(10)],
    )
    assert context["truncated"] is True
