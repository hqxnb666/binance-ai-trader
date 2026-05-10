from __future__ import annotations

from ai.context_builder import build_audit_context
from config.settings import load_settings


def test_auditor_permissions_are_forced_false_even_if_env_true(monkeypatch) -> None:
    monkeypatch.setenv("SYSTEM_AUDITOR_AUTO_FIX_ALLOWED", "true")
    monkeypatch.setenv("SYSTEM_AUDITOR_CAN_CALL_CODEX", "true")
    monkeypatch.setenv("SYSTEM_AUDITOR_CAN_MODIFY_CONFIG", "true")
    monkeypatch.setenv("SYSTEM_AUDITOR_CAN_MODIFY_STRATEGY", "true")
    monkeypatch.setenv("SYSTEM_AUDITOR_CAN_PLACE_ORDER", "true")
    settings = load_settings()

    assert settings.system_auditor_auto_fix_allowed is False
    assert settings.system_auditor_can_call_codex is False
    assert settings.system_auditor_can_modify_config is False
    assert settings.system_auditor_can_modify_strategy is False
    assert settings.system_auditor_can_place_order is False

    context = build_audit_context(
        settings=settings,
        runtime_health={},
        budget_status={},
    )
    guardrails = context["security_guardrails"]
    assert guardrails["auditor_auto_fix_allowed"] is False
    assert guardrails["auditor_can_call_codex"] is False
    assert guardrails["auditor_can_modify_config"] is False
    assert guardrails["auditor_can_modify_strategy"] is False
    assert guardrails["auditor_can_place_order"] is False
