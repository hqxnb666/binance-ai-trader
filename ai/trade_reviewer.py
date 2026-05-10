from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ai.budget_guard import BudgetGuard
from ai.model_router import OpenAIModelRole, resolve_max_output_tokens, resolve_openai_model
from ai.openai_client import StructuredOpenAIClient
from ai.prompts import TRADE_REVIEW_SYSTEM_PROMPT
from ai.schemas import TradeReview
from config.settings import Settings


class TradeReviewer:
    def __init__(self, settings: Settings, client: StructuredOpenAIClient | None = None):
        self.settings = settings
        self.role = OpenAIModelRole.TRADE_REVIEW
        self.model = resolve_openai_model(settings, self.role)
        self.max_output_tokens = resolve_max_output_tokens(settings, self.role)
        self.client = client or StructuredOpenAIClient(
            api_key=settings.openai_api_key,
            model=self.model,
            role=self.role,
            usage_ledger_enabled=settings.enable_openai_usage_ledger,
        )

    def review(self, payload: dict[str, Any], usage_session: Session | None = None) -> TradeReview:
        if not self.settings.ai_analysis_enabled:
            return TradeReview(
                grade="C",
                entry_quality="average",
                exit_quality="not_applicable",
                mistake_tag="none",
                main_reason="AI analysis disabled",
                improvement_candidate="Review trade manually before changing strategy.",
                requires_backtest=True,
            )
        if usage_session is not None:
            budget_guard = BudgetGuard(self.settings, usage_session)
            decision = budget_guard.check_before_openai_call(role=self.role, model=self.model)
            if not decision.allowed:
                reason = ",".join(decision.reason_codes) or "BUDGET_GUARD_BLOCKED"
                budget_guard.record_skipped_budget(
                    role=self.role,
                    model=self.model,
                    operation_name="trade_review",
                    reason=reason,
                    input_payload=payload,
                )
                return TradeReview(
                    grade="C",
                    entry_quality="average",
                    exit_quality="not_applicable",
                    mistake_tag="none",
                    main_reason=f"Trade review skipped by BudgetGuard: {reason}",
                    improvement_candidate="Review trade manually before changing strategy.",
                    requires_backtest=True,
                )
        return self.client.parse(
            system_prompt=TRADE_REVIEW_SYSTEM_PROMPT,
            user_payload=payload,
            schema=TradeReview,
            role=self.role,
            model_override=self.model,
            max_output_tokens=self.max_output_tokens,
            usage_session=usage_session,
            operation_name="trade_review",
        )
