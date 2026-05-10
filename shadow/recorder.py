from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from config.settings import Settings
from shadow.schemas import (
    ShadowContextSummary,
    ShadowDecision,
    ShadowDecisionStatus,
    ShadowDecisionType,
)
from shadow.store import create_shadow_decision


class ShadowModeRecorder:
    """Records simulated decisions; it never places orders or changes trading state."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def enabled(self, *, dry_run: bool, order_execution_enabled: bool) -> bool:
        if not self.settings.enable_shadow_mode:
            return False
        real_order_path = order_execution_enabled and not dry_run
        if real_order_path and self.settings.shadow_mode_disable_when_real_order_enabled:
            return False
        return not (dry_run and not self.settings.shadow_mode_allow_when_dry_run)

    def record(
        self,
        session: Session,
        *,
        decision_type: ShadowDecisionType,
        symbol: str,
        side: str = "HOLD",
        reason: str,
        reason_codes: list[str] | None = None,
        context_summary: dict[str, Any] | None = None,
        strategy_plan_id: str | int | None = None,
        signal_review_id: str | int | None = None,
        risk_decision_id: str | int | None = None,
        data_quality_snapshot_id: str | int | None = None,
        order_type: str | None = None,
        simulated_entry_price: Decimal | str | None = None,
        simulated_quantity: Decimal | str | None = None,
        simulated_notional: Decimal | str | None = None,
        dry_run: bool,
        order_execution_enabled: bool,
    ):
        if not self.enabled(dry_run=dry_run, order_execution_enabled=order_execution_enabled):
            return None
        if self.settings.shadow_mode_record_approved_only and (
            decision_type != ShadowDecisionType.WOULD_PLACE_ORDER
        ):
            return None
        if (
            decision_type != ShadowDecisionType.WOULD_PLACE_ORDER
            and not self.settings.shadow_mode_record_rejected_signals
        ):
            return None
        now = datetime.now(UTC)
        would_submit = decision_type == ShadowDecisionType.WOULD_PLACE_ORDER
        decision = ShadowDecision(
            shadow_id=f"shadow-{uuid.uuid4().hex[:20]}",
            created_at=now,
            status=ShadowDecisionStatus.CREATED,
            decision_type=decision_type,
            symbol=symbol.upper(),
            side=side.upper(),
            strategy_plan_id=_id_or_none(strategy_plan_id),
            signal_review_id=_id_or_none(signal_review_id),
            risk_decision_id=_id_or_none(risk_decision_id),
            data_quality_snapshot_id=_id_or_none(data_quality_snapshot_id),
            order_would_be_submitted=would_submit,
            order_type=order_type,
            simulated_entry_price=_decimal_or_none(simulated_entry_price),
            simulated_quantity=_decimal_or_none(simulated_quantity),
            simulated_notional=_decimal_or_none(simulated_notional),
            reason=reason[:1000],
            reason_codes=(reason_codes or [])[:20],
            context_summary=ShadowContextSummary.model_validate(
                _context_summary(context_summary or {})
            ),
            expires_at=now
            + timedelta(minutes=max(self.settings.shadow_mode_simulated_hold_minutes, 1)),
            dry_run=dry_run,
            order_execution_enabled=order_execution_enabled,
        )
        return create_shadow_decision(session, decision)

    def record_would_place_order(self, session: Session, **kwargs: Any):
        return self.record(session, decision_type=ShadowDecisionType.WOULD_PLACE_ORDER, **kwargs)

    def record_ai_rejected(self, session: Session, **kwargs: Any):
        return self.record(session, decision_type=ShadowDecisionType.AI_REJECTED, **kwargs)

    def record_risk_rejected(self, session: Session, **kwargs: Any):
        return self.record(session, decision_type=ShadowDecisionType.RISK_REJECTED, **kwargs)

    def record_data_quality_blocked(self, session: Session, **kwargs: Any):
        return self.record(session, decision_type=ShadowDecisionType.DATA_QUALITY_BLOCKED, **kwargs)

    def record_strategy_no_trade(self, session: Session, **kwargs: Any):
        return self.record(session, decision_type=ShadowDecisionType.STRATEGY_NO_TRADE, **kwargs)

    def record_budget_blocked(self, session: Session, **kwargs: Any):
        return self.record(session, decision_type=ShadowDecisionType.BUDGET_BLOCKED, **kwargs)


def _id_or_none(value: str | int | None) -> str | None:
    return None if value is None else str(value)


def _decimal_or_none(value: Decimal | str | None) -> str | None:
    if value is None:
        return None
    return format(Decimal(str(value)), "f")


def _context_summary(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "strategy_name": _str_or_none(raw.get("strategy_name")),
        "signal_type": _str_or_none(raw.get("signal_type")),
        "ai_decision": _str_or_none(raw.get("ai_decision")),
        "risk_reason": _str_or_none(raw.get("risk_reason")),
        "data_quality_status": _str_or_none(raw.get("data_quality_status")),
        "price_source": _str_or_none(raw.get("price_source")),
        "notes": [str(item)[:300] for item in list(raw.get("notes", []))[:10]],
    }


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)[:300]
