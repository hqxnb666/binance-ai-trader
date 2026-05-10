from __future__ import annotations

import json

from ai.context_builder import build_signal_review_context, build_strategy_context
from config.settings import load_settings


def test_strategy_context_safe_unknown_and_json_serializable(monkeypatch) -> None:
    monkeypatch.setenv("AI_CONTEXT_MAX_JSON_CHARS", "24000")
    settings = load_settings()
    context = build_strategy_context(
        settings,
        ["BTCUSDT"],
        {"BTCUSDT": {"symbol": "BTCUSDT", "OPENAI_API_KEY": "sk-secret"}},
        active_strategy_plan=None,
    )
    rendered = json.dumps(context)
    assert context["account_state"]["status"] == "unknown"
    assert "sk-secret" not in rendered
    assert "OPENAI_API_KEY" in rendered


def test_strategy_context_simulated_defaults_are_labeled() -> None:
    settings = load_settings()
    context = build_strategy_context(
        settings,
        ["BTCUSDT"],
        {},
        None,
        account_state={"status": "simulated_or_unknown", "source": "simulated_default"},
    )
    assert context["account_state"]["source"] == "simulated_default"


def test_strategy_context_truncates_long_lists(monkeypatch) -> None:
    monkeypatch.setenv("AI_CONTEXT_RECENT_SIGNAL_REVIEWS_LIMIT", "2")
    settings = load_settings()
    context = build_strategy_context(
        settings,
        ["BTCUSDT"],
        {},
        None,
        recent_summary={"signal_reviews": [{"id": idx} for idx in range(5)]},
    )
    assert [item["id"] for item in context["recent_signal_reviews"]] == [3, 4]


def test_context_marks_truncated_when_json_too_large(monkeypatch) -> None:
    monkeypatch.setenv("AI_CONTEXT_MAX_JSON_CHARS", "1000")
    settings = load_settings()
    context = build_strategy_context(
        settings,
        ["BTCUSDT"],
        {"BTCUSDT": {"symbol": "BTCUSDT", "blob": "x" * 10000}},
        None,
    )
    assert context["truncated"] is True


def test_signal_review_context_contains_budget_and_flags() -> None:
    context = build_signal_review_context(
        {"symbol": "BTCUSDT"},
        {"side": "BUY"},
        {"id": 1, "risk_mode": "conservative"},
        budget_status={"budget_blocked": False},
        data_quality_flags=["ok"],
    )
    assert context["signal_review_context"]["budget_status"]["budget_blocked"] is False
    assert context["signal_review_context"]["data_quality_flags"] == ["ok"]
