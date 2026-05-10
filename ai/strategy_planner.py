from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from ai.budget_guard import BudgetGuard
from ai.model_router import OpenAIModelRole, resolve_max_output_tokens, resolve_openai_model
from ai.openai_client import StructuredOpenAIClient
from ai.prompts import STRATEGY_PLANNER_PROMPT_VERSION, load_strategy_planner_prompt
from ai.strategy_schemas import (
    FORBIDDEN_ORDER_FIELDS,
    EntryQuality,
    MarketRegime,
    RiskMode,
    StrategyPlan,
    StrategyPlanAction,
    StrategyPlanningMode,
    StrategyPlanUpdate,
    SymbolPermission,
    TradeBias,
)
from config.settings import Settings


@dataclass(frozen=True)
class StrategyPlannerResult:
    output: StrategyPlan | StrategyPlanUpdate
    schema_valid: bool
    reason: str
    model: str
    role: OpenAIModelRole
    planning_mode: StrategyPlanningMode
    max_output_tokens: int | None
    prompt_version: str = STRATEGY_PLANNER_PROMPT_VERSION


class StrategyPlanner:
    def __init__(self, settings: Settings, client: StructuredOpenAIClient | None = None):
        self.settings = settings
        self.role = OpenAIModelRole.STRATEGY_PLANNER
        self.model = resolve_openai_model(settings, self.role)
        self.max_output_tokens = resolve_max_output_tokens(settings, self.role)
        self.client = client or StructuredOpenAIClient(
            api_key=settings.openai_api_key,
            model=self.model,
            role=self.role,
            usage_ledger_enabled=settings.enable_openai_usage_ledger,
        )
        self.system_prompt = load_strategy_planner_prompt()

    def plan(
        self,
        *,
        planning_mode: StrategyPlanningMode,
        context: dict[str, Any],
        active_plan_id: str | None = None,
        usage_session: Session | None = None,
    ) -> StrategyPlannerResult:
        schema: type[StrategyPlan] | type[StrategyPlanUpdate]
        if planning_mode == StrategyPlanningMode.FULL_REPLAN:
            schema = StrategyPlan
        else:
            schema = StrategyPlanUpdate
        payload = {**context, "planning_mode": planning_mode.value}
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
                    operation_name=f"strategy_planner.{planning_mode.value.lower()}",
                    reason=reason,
                    input_payload=payload,
                )
                output = budget_blocked_strategy_output(
                    planning_mode=planning_mode,
                    previous_plan_id=active_plan_id,
                    has_active_plan=active_plan_id is not None,
                    explanation=f"Strategy planner blocked by BudgetGuard: {reason}",
                )
                return StrategyPlannerResult(
                    output=output,
                    schema_valid=False,
                    reason=reason,
                    model=self.model,
                    role=self.role,
                    planning_mode=planning_mode,
                    max_output_tokens=self.max_output_tokens,
                )
        try:
            output = self.client.parse(
                system_prompt=self.system_prompt,
                user_payload=payload,
                schema=schema,
                role=self.role,
                model_override=self.model,
                max_output_tokens=self.max_output_tokens,
                reasoning_effort="low",
                usage_session=usage_session,
                operation_name=f"strategy_planner.{planning_mode.value.lower()}",
            )
            if not isinstance(output, schema):
                msg = "Strategy planner returned an object that did not match schema"
                raise ValueError(msg)
            return StrategyPlannerResult(
                output=output,
                schema_valid=True,
                reason="strategy planner completed",
                model=self.model,
                role=self.role,
                planning_mode=planning_mode,
                max_output_tokens=self.max_output_tokens,
            )
        except (ValidationError, ValueError, RuntimeError) as exc:
            output = fail_closed_strategy_output(
                planning_mode=planning_mode,
                previous_plan_id=active_plan_id,
                reason_code="STRATEGY_SCHEMA_INVALID"
                if isinstance(exc, ValidationError | ValueError)
                else "AI_STRATEGY_PLANNER_FAILED",
                explanation=f"Strategy planner failed closed: {exc}",
            )
            return StrategyPlannerResult(
                output=output,
                schema_valid=False,
                reason=str(exc),
                model=self.model,
                role=self.role,
                planning_mode=planning_mode,
                max_output_tokens=self.max_output_tokens,
            )


def fail_closed_strategy_output(
    *,
    planning_mode: StrategyPlanningMode,
    previous_plan_id: str | None,
    reason_code: str,
    explanation: str,
) -> StrategyPlan | StrategyPlanUpdate:
    expires_at = datetime.now(UTC) + timedelta(minutes=30)
    if planning_mode == StrategyPlanningMode.FULL_REPLAN:
        return StrategyPlan(
            schema_version="strategy_plan_v1",
            plan_action="CREATE",
            planning_mode="FULL_REPLAN",
            symbol_scope=["BTCUSDT", "ETHUSDT"],
            market_regime=MarketRegime.UNCERTAIN,
            trade_bias=TradeBias.NO_TRADE,
            allowed_actions=[],
            blocked_actions=["MARTINGALE", "LEVERAGE", "SHORT", "BUY", "SELL"],
            risk_mode=RiskMode.NO_TRADE,
            max_position_pct=0,
            symbol_permissions=[
                {
                    "symbol": "BTCUSDT",
                    "permission": SymbolPermission.BLOCKED,
                    "reason": "AI strategy planner failed closed",
                },
                {
                    "symbol": "ETHUSDT",
                    "permission": SymbolPermission.BLOCKED,
                    "reason": "AI strategy planner failed closed",
                },
            ],
            entry_quality_required=EntryQuality.VERY_HIGH,
            invalidation_conditions=["AI strategy planner failed closed"],
            expires_at=expires_at,
            confidence=0,
            requires_human_review=True,
            reason_codes=[reason_code],
            explanation=_safe_strategy_explanation(explanation),
        )
    return StrategyPlanUpdate(
        schema_version="strategy_plan_update_v1",
        plan_action=StrategyPlanAction.NO_TRADE,
        planning_mode=planning_mode,
        previous_plan_id=previous_plan_id,
        is_previous_plan_still_valid=False,
        changes=[],
        new_expiration_time=expires_at,
        confidence=0,
        requires_human_review=True,
        reason_codes=[reason_code],
        explanation=_safe_strategy_explanation(explanation),
    )


def budget_blocked_strategy_output(
    *,
    planning_mode: StrategyPlanningMode,
    previous_plan_id: str | None,
    has_active_plan: bool,
    explanation: str,
) -> StrategyPlan | StrategyPlanUpdate:
    if planning_mode != StrategyPlanningMode.FULL_REPLAN and has_active_plan:
        return StrategyPlanUpdate(
            schema_version="strategy_plan_update_v1",
            plan_action=StrategyPlanAction.KEEP,
            planning_mode=planning_mode,
            previous_plan_id=previous_plan_id,
            is_previous_plan_still_valid=True,
            changes=[],
            new_expiration_time=None,
            confidence=0,
            requires_human_review=True,
            reason_codes=["BUDGET_GUARD_BLOCKED"],
            explanation=_safe_strategy_explanation(explanation),
        )
    return fail_closed_strategy_output(
        planning_mode=StrategyPlanningMode.FULL_REPLAN
        if planning_mode == StrategyPlanningMode.FULL_REPLAN
        else planning_mode,
        previous_plan_id=previous_plan_id,
        reason_code="BUDGET_GUARD_BLOCKED",
        explanation=explanation,
    )


def _safe_strategy_explanation(value: str) -> str:
    safe = value
    for field_name in FORBIDDEN_ORDER_FIELDS:
        safe = safe.replace(field_name, "[REDACTED_ORDER_FIELD]")
    return safe[:1000]
