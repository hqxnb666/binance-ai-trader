from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from ai.budget_guard import BudgetGuard
from ai.context_builder import build_signal_review_context, summarize_strategy_plan
from ai.model_router import OpenAIModelRole, resolve_max_output_tokens, resolve_openai_model
from ai.openai_client import StructuredOpenAIClient
from ai.prompts import SIGNAL_REVIEW_PROMPT_VERSION, SIGNAL_REVIEW_SYSTEM_PROMPT
from ai.schemas import (
    MarketRegime,
    RiskLevel,
    SignalDecision,
    SignalReview,
    SignalSide,
    signal_review_trade_gate,
)
from config.settings import Settings


@dataclass(frozen=True)
class SignalReviewResult:
    review: SignalReview
    approved_for_risk: bool
    reason: str
    schema_valid: bool
    actual_model: str
    active_strategy_plan_id: int | str | None = None
    input_payload: dict[str, Any] | None = None


class SignalReviewer:
    def __init__(self, settings: Settings, client: StructuredOpenAIClient | None = None):
        self.settings = settings
        self.role = OpenAIModelRole.SIGNAL_REVIEW
        self.model = resolve_openai_model(settings, self.role)
        self.max_output_tokens = resolve_max_output_tokens(settings, self.role)
        self.client = client or StructuredOpenAIClient(
            api_key=settings.openai_api_key,
            model=self.model,
            role=self.role,
            usage_ledger_enabled=settings.enable_openai_usage_ledger,
        )

    def review_with_schema(
        self,
        snapshot: dict[str, Any],
        *,
        active_strategy_plan: dict[str, Any] | Any | None = None,
        signal_review_context: dict[str, Any] | None = None,
        usage_session: Session | None = None,
    ) -> SignalReviewResult:
        plan_summary = summarize_strategy_plan(active_strategy_plan)
        payload = signal_review_context or build_signal_review_context(
            current_snapshot=snapshot,
            candidate_signal=snapshot.get("strategy_signal"),
            active_strategy_plan=plan_summary,
        )
        if _strategy_plan_blocks_signal(payload):
            review = _human_review(payload, "Active StrategyPlan blocks or observes this signal")
            return SignalReviewResult(
                review,
                False,
                "Active StrategyPlan blocks or observes this signal",
                True,
                self.model,
                (plan_summary or {}).get("id"),
                payload,
            )
        if not self.settings.ai_analysis_enabled:
            review = _human_review(payload, "AI analysis disabled")
            return SignalReviewResult(
                review, False, "AI analysis disabled", False, self.model, None, payload
            )
        if usage_session is not None:
            budget_guard = BudgetGuard(self.settings, usage_session)
            budget_decision = budget_guard.check_before_openai_call(
                role=self.role,
                model=self.model,
            )
            if not budget_decision.allowed:
                reason = ",".join(budget_decision.reason_codes) or "BUDGET_GUARD_BLOCKED"
                budget_guard.record_skipped_budget(
                    role=self.role,
                    model=self.model,
                    operation_name="signal_review",
                    reason=reason,
                    input_payload=payload,
                )
                review = _human_review(
                    payload, f"BudgetGuard blocked SignalReview: {reason}"
                ).model_copy(update={"side": SignalSide.HOLD})
                return SignalReviewResult(
                    review,
                    False,
                    "BUDGET_GUARD_BLOCKED",
                    False,
                    self.model,
                    (plan_summary or {}).get("id"),
                    payload,
                )
        try:
            review = self.client.parse(
                system_prompt=SIGNAL_REVIEW_SYSTEM_PROMPT,
                user_payload=payload,
                schema=SignalReview,
                role=self.role,
                model_override=self.model,
                max_output_tokens=self.max_output_tokens,
                usage_session=usage_session,
                operation_name="signal_review",
            )
            approved, reason = signal_review_trade_gate(review)
            return SignalReviewResult(
                review,
                approved,
                reason,
                True,
                self.model,
                (plan_summary or {}).get("id"),
                payload,
            )
        except (ValidationError, ValueError, RuntimeError) as exc:
            review = _human_review(payload, f"AI schema or call failed: {exc}")
            return SignalReviewResult(review, False, str(exc), False, self.model, None, payload)

    def review(self, snapshot: dict[str, Any]) -> tuple[SignalReview, bool, str]:
        result = self.review_with_schema(snapshot)
        return result.review, result.approved_for_risk, result.reason

    @staticmethod
    def analysis_payload(
        *,
        snapshot: dict[str, Any],
        review: SignalReview,
        schema_valid: bool,
        model: str,
    ) -> dict[str, Any]:
        return {
            "symbol": snapshot.get("symbol", "UNKNOWN"),
            "analysis_type": "signal_review",
            "model": model,
            "prompt_version": SIGNAL_REVIEW_PROMPT_VERSION,
            "input_json": snapshot,
            "output_json": review.model_dump(mode="json"),
            "schema_valid": schema_valid,
            "decision": review.decision.value,
            "confidence": review.confidence,
            "risk_level": review.risk_level.value,
        }


def _human_review(snapshot: dict[str, Any], reason: str) -> SignalReview:
    side = snapshot.get("strategy_signal", {}).get("side", "HOLD") if snapshot else "HOLD"
    if side not in {"BUY", "SELL", "HOLD"}:
        side = "HOLD"
    return SignalReview(
        decision=SignalDecision.HUMAN_REVIEW_REQUIRED,
        symbol=str(snapshot.get("symbol", "UNKNOWN")),
        side=SignalSide(side),
        confidence=0,
        risk_level=RiskLevel.HIGH,
        market_regime=MarketRegime.UNCLEAR,
        reason=reason[:500],
        warnings=[reason[:200]],
        max_position_pct=0,
        requires_human_review=True,
    )


def _strategy_plan_blocks_signal(payload: dict[str, Any]) -> bool:
    context = payload.get("signal_review_context", {})
    if not isinstance(context, dict):
        return False
    plan = context.get("active_strategy_plan")
    if not isinstance(plan, dict):
        return False
    if plan.get("risk_mode") == "no_trade" or plan.get("trade_bias") == "no_trade":
        return True
    symbol = str(
        payload.get("symbol") or payload.get("market_snapshot", {}).get("symbol", "")
    ).upper()
    permissions = plan.get("symbol_permissions", {})
    return isinstance(permissions, dict) and permissions.get(symbol) in {
        "observe_only",
        "blocked",
    }
