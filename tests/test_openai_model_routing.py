from __future__ import annotations

from ai.model_router import OpenAIModelRole, configured_models, resolve_openai_model
from config.settings import load_settings


def test_role_default_models() -> None:
    settings = load_settings()
    assert resolve_openai_model(settings, OpenAIModelRole.STRATEGY_PLANNER) == "gpt-5.5"
    assert resolve_openai_model(settings, OpenAIModelRole.SIGNAL_REVIEW) == "gpt-5.4-mini"
    assert resolve_openai_model(settings, OpenAIModelRole.DIAGNOSTIC) == "gpt-5.4-nano"


def test_legacy_openai_model_fallback(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_STRATEGY_MODEL", "")
    monkeypatch.setenv("OPENAI_DEFAULT_MODEL", "")
    monkeypatch.setenv("OPENAI_MODEL", "legacy-model")
    settings = load_settings()
    assert resolve_openai_model(settings, OpenAIModelRole.STRATEGY_PLANNER) == "legacy-model"


def test_defaults_do_not_use_old_or_pro_models() -> None:
    settings = load_settings()
    rendered = str(configured_models(settings))
    assert "gpt-5.1-mini" not in rendered
    assert settings.openai_enable_model_fallback is False
    assert "gpt-5.5-pro" not in settings.openai_fallback_models
    assert "gpt-5.4-pro" not in settings.openai_fallback_models
