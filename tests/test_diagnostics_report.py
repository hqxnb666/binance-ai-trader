from __future__ import annotations

import json

from config.settings import load_settings
from diagnostics.openai_access import check_openai_api
from diagnostics.report import save_diagnostics_report


def test_diagnostics_report_can_be_saved(tmp_path, monkeypatch) -> None:
    import diagnostics.report as report_module

    monkeypatch.setattr(report_module, "REPORT_DIR", tmp_path)
    report = {
        "environment": {"proxy_env": {}, "required_env": {}},
        "connectivity": {},
        "openai_budget": {"enabled": True},
        "readiness": {},
        "recommended_next_action": [],
        "created_at": "now",
    }
    path = save_diagnostics_report(report)
    assert path.exists()
    assert path.suffix == ".json"


def test_openai_diagnostics_include_configured_models_without_secret(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "your_openai_key_here")
    monkeypatch.setenv("OPENAI_STRATEGY_MODEL", "gpt-5.5")
    monkeypatch.setenv("OPENAI_SIGNAL_MODEL", "gpt-5.4-mini")
    settings = load_settings()

    result = check_openai_api(settings)
    rendered = json.dumps(result)

    assert result["status"] == "MISSING_KEY"
    assert result["configured_models"]["strategy_planner"] == "gpt-5.5"
    assert result["configured_models"]["signal_review"] == "gpt-5.4-mini"
    assert "your_openai_key_here" not in rendered
    assert "sk-" not in rendered
