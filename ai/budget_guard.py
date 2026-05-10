from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from ai.model_router import OpenAIModelRole
from config.settings import Settings
from journal.openai_usage_store import (
    get_month_openai_cost,
    get_role_call_count_today,
    get_today_openai_cost,
    record_openai_usage,
)


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    reason_codes: list[str]
    daily_cost_usd: Decimal
    monthly_cost_usd: Decimal
    role_call_count_today: int
    budget_limit: dict[str, float | int]
    fallback_allowed: bool = False


class BudgetGuard:
    def __init__(self, settings: Settings, session: Session):
        self.settings = settings
        self.session = session

    def check_before_openai_call(
        self,
        *,
        role: OpenAIModelRole | str,
        model: str,
    ) -> BudgetDecision:
        role_value = _role_value(role)
        if not self.settings.enable_budget_guard:
            return BudgetDecision(
                allowed=True,
                reason_codes=["BUDGET_GUARD_DISABLED"],
                daily_cost_usd=Decimal("0"),
                monthly_cost_usd=Decimal("0"),
                role_call_count_today=0,
                budget_limit=self._limits(role_value),
                fallback_allowed=False,
            )
        daily_cost = get_today_openai_cost(self.session)
        monthly_cost = get_month_openai_cost(self.session)
        role_count = get_role_call_count_today(self.session, role_value)
        reason_codes: list[str] = []
        if daily_cost >= Decimal(str(self.settings.openai_daily_budget_usd)):
            reason_codes.append("OPENAI_DAILY_BUDGET_EXCEEDED")
        if monthly_cost >= Decimal(str(self.settings.openai_monthly_budget_usd)):
            reason_codes.append("OPENAI_MONTHLY_BUDGET_EXCEEDED")
        role_limit = self._role_limit(role_value)
        if role_limit is not None and role_count >= role_limit:
            reason_codes.append(f"{role_value.upper()}_DAILY_CALL_LIMIT_EXCEEDED")
        allowed = not reason_codes or not self.settings.openai_fail_closed_on_budget_exceeded
        return BudgetDecision(
            allowed=allowed,
            reason_codes=reason_codes,
            daily_cost_usd=daily_cost,
            monthly_cost_usd=monthly_cost,
            role_call_count_today=role_count,
            budget_limit=self._limits(role_value),
            fallback_allowed=False,
        )

    def record_skipped_budget(
        self,
        *,
        role: OpenAIModelRole | str,
        model: str,
        operation_name: str,
        reason: str,
        input_payload: dict[str, object] | None = None,
    ) -> None:
        if not self.settings.enable_openai_usage_ledger:
            return
        record_openai_usage(
            self.session,
            role=_role_value(role),
            model=model,
            operation_name=operation_name,
            status="SKIPPED_BUDGET",
            error_type="BudgetGuardBlocked",
            error_message=reason,
            input_payload=input_payload,
        )

    def record_after_openai_call(
        self,
        *,
        role: OpenAIModelRole | str,
        model: str,
        operation_name: str,
        status: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cached_tokens: int | None = None,
        total_tokens: int | None = None,
        latency_ms: int | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
        input_payload: dict[str, object] | None = None,
        output_payload: dict[str, object] | None = None,
    ) -> None:
        if not self.settings.enable_openai_usage_ledger:
            return
        record_openai_usage(
            self.session,
            role=_role_value(role),
            model=model,
            operation_name=operation_name,
            status=status,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            error_type=error_type,
            error_message=error_message,
            input_payload=input_payload,
            output_payload=output_payload,
        )

    def _role_limit(self, role: str) -> int | None:
        if role == OpenAIModelRole.STRATEGY_PLANNER.value:
            return self.settings.openai_strategy_daily_call_limit
        if role == OpenAIModelRole.SIGNAL_REVIEW.value:
            return self.settings.openai_signal_daily_call_limit
        return None

    def _limits(self, role: str) -> dict[str, float | int]:
        return {
            "daily_budget_usd": self.settings.openai_daily_budget_usd,
            "monthly_budget_usd": self.settings.openai_monthly_budget_usd,
            "role_daily_call_limit": self._role_limit(role) or 0,
        }


def budget_status(settings: Settings, session: Session | None) -> dict[str, object]:
    if session is None:
        return {
            "budget_guard_enabled": settings.enable_budget_guard,
            "usage_ledger_enabled": settings.enable_openai_usage_ledger,
            "openai_today_cost_usd": "unknown",
            "openai_month_cost_usd": "unknown",
            "strategy_calls_today": "unknown",
            "signal_calls_today": "unknown",
            "budget_blocked": False,
        }
    try:
        today = get_today_openai_cost(session)
        month = get_month_openai_cost(session)
        strategy_calls = get_role_call_count_today(
            session, OpenAIModelRole.STRATEGY_PLANNER.value
        )
        signal_calls = get_role_call_count_today(session, OpenAIModelRole.SIGNAL_REVIEW.value)
        blocked = (
            today >= Decimal(str(settings.openai_daily_budget_usd))
            or month >= Decimal(str(settings.openai_monthly_budget_usd))
            or strategy_calls >= settings.openai_strategy_daily_call_limit
            or signal_calls >= settings.openai_signal_daily_call_limit
        )
        return {
            "budget_guard_enabled": settings.enable_budget_guard,
            "usage_ledger_enabled": settings.enable_openai_usage_ledger,
            "openai_today_cost_usd": float(today),
            "openai_month_cost_usd": float(month),
            "strategy_calls_today": strategy_calls,
            "signal_calls_today": signal_calls,
            "daily_budget_usd": settings.openai_daily_budget_usd,
            "monthly_budget_usd": settings.openai_monthly_budget_usd,
            "budget_blocked": blocked and settings.openai_fail_closed_on_budget_exceeded,
        }
    except Exception as exc:  # noqa: BLE001 - health/diagnostics must not crash
        return {
            "budget_guard_enabled": settings.enable_budget_guard,
            "usage_ledger_enabled": settings.enable_openai_usage_ledger,
            "openai_today_cost_usd": "unknown",
            "openai_month_cost_usd": "unknown",
            "strategy_calls_today": "unknown",
            "signal_calls_today": "unknown",
            "budget_blocked": False,
            "warning": f"OpenAI usage ledger unavailable: {type(exc).__name__}",
        }


def _role_value(role: OpenAIModelRole | str) -> str:
    return role.value if isinstance(role, OpenAIModelRole) else str(role)
