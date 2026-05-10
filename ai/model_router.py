from __future__ import annotations

from enum import StrEnum

from config.settings import Settings

DEFAULT_OPENAI_MODEL = "gpt-5.4-nano"


class OpenAIModelRole(StrEnum):
    DIAGNOSTIC = "diagnostic"
    STRATEGY_PLANNER = "strategy_planner"
    SIGNAL_REVIEW = "signal_review"
    TRADE_REVIEW = "trade_review"
    DAILY_REPORT = "daily_report"
    SYSTEM_AUDITOR = "system_auditor"
    DEEP_AUDITOR = "deep_auditor"


def resolve_openai_model(settings: Settings, role: OpenAIModelRole) -> str:
    role_specific = {
        OpenAIModelRole.DIAGNOSTIC: settings.openai_diagnostic_model,
        OpenAIModelRole.STRATEGY_PLANNER: settings.openai_strategy_model,
        OpenAIModelRole.SIGNAL_REVIEW: settings.openai_signal_model,
        OpenAIModelRole.TRADE_REVIEW: settings.openai_trade_review_model,
        OpenAIModelRole.DAILY_REPORT: settings.openai_daily_report_model,
        OpenAIModelRole.SYSTEM_AUDITOR: settings.openai_system_auditor_model,
        OpenAIModelRole.DEEP_AUDITOR: settings.openai_deep_auditor_model,
    }[role]
    for candidate in (
        role_specific,
        settings.openai_default_model,
        settings.openai_model,
        DEFAULT_OPENAI_MODEL,
    ):
        if candidate and candidate.strip():
            return candidate.strip()
    return DEFAULT_OPENAI_MODEL


def resolve_max_output_tokens(settings: Settings, role: OpenAIModelRole) -> int | None:
    tokens = {
        OpenAIModelRole.DIAGNOSTIC: settings.openai_diagnostic_max_output_tokens,
        OpenAIModelRole.STRATEGY_PLANNER: settings.openai_strategy_max_output_tokens,
        OpenAIModelRole.SIGNAL_REVIEW: settings.openai_signal_max_output_tokens,
        OpenAIModelRole.TRADE_REVIEW: settings.openai_trade_review_max_output_tokens,
        OpenAIModelRole.DAILY_REPORT: settings.openai_daily_report_max_output_tokens,
        OpenAIModelRole.SYSTEM_AUDITOR: settings.openai_system_auditor_max_output_tokens,
        OpenAIModelRole.DEEP_AUDITOR: settings.openai_deep_auditor_max_output_tokens,
    }[role]
    return tokens if tokens and tokens > 0 else None


def configured_models(settings: Settings) -> dict[str, str]:
    return {
        role.value: resolve_openai_model(settings, role)
        for role in OpenAIModelRole
    }
