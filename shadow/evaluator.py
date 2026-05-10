from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from config.settings import Settings
from journal.models import MarketKline
from shadow.schemas import ShadowDecisionStatus, ShadowEvaluation, ShadowExitReason
from shadow.store import (
    add_shadow_evaluation,
    close_shadow_decision,
    latest_evaluation_for_shadow,
    list_open_shadow_decisions,
    shadow_evaluation_to_dict,
)


class ShadowModeEvaluator:
    """Evaluates simulated shadow trades from market prices; it never places orders."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def evaluate_open_decisions(
        self,
        session: Session,
        *,
        current_prices: dict[str, Decimal] | None = None,
    ) -> list[dict[str, Any]]:
        if not self.settings.enable_shadow_mode:
            return []
        prices = current_prices or latest_prices_from_db(session)
        results: list[dict[str, Any]] = []
        for decision in list_open_shadow_decisions(
            session,
            limit=self.settings.shadow_mode_max_open_shadow_trades,
            would_place_only=True,
        ):
            price = prices.get(decision.symbol)
            if price is None:
                continue
            evaluation = self._evaluate_one(session, decision, price)
            results.append(shadow_evaluation_to_dict(evaluation))
        return results

    def _evaluate_one(self, session: Session, decision: Any, current_price: Decimal):
        now = datetime.now(UTC)
        if decision.side == "SELL":
            evaluation = ShadowEvaluation(
                shadow_id=decision.shadow_id,
                evaluated_at=now,
                current_price=format(current_price, "f"),
                minutes_since_entry=_minutes_since(decision.created_at, now),
                unrealized_pnl_usdt="0",
                unrealized_pnl_pct=0,
                mfe_usdt="0",
                mae_usdt="0",
                status=ShadowDecisionStatus.INVALIDATED,
                exit_reason=ShadowExitReason.INVALIDATED,
            )
            record = add_shadow_evaluation(session, evaluation)
            close_shadow_decision(
                session,
                decision.shadow_id,
                status=ShadowDecisionStatus.INVALIDATED,
            )
            return record
        entry = Decimal(str(decision.simulated_entry_price or "0"))
        quantity = Decimal(str(decision.simulated_quantity or "0"))
        notional = Decimal(str(decision.simulated_notional or "0"))
        if entry <= 0 or quantity <= 0:
            evaluation = ShadowEvaluation(
                shadow_id=decision.shadow_id,
                evaluated_at=now,
                current_price=format(current_price, "f"),
                minutes_since_entry=_minutes_since(decision.created_at, now),
                unrealized_pnl_usdt="0",
                unrealized_pnl_pct=0,
                mfe_usdt="0",
                mae_usdt="0",
                status=ShadowDecisionStatus.INVALIDATED,
                exit_reason=ShadowExitReason.INVALIDATED,
            )
            record = add_shadow_evaluation(session, evaluation)
            close_shadow_decision(
                session,
                decision.shadow_id,
                status=ShadowDecisionStatus.INVALIDATED,
            )
            return record
        pnl = (current_price - entry) * quantity
        denominator = notional if notional > 0 else entry * quantity
        pnl_pct = float((pnl / denominator) * Decimal("100")) if denominator > 0 else 0.0
        previous = latest_evaluation_for_shadow(session, decision.shadow_id)
        previous_mfe = Decimal(str(previous.mfe_usdt)) if previous else pnl
        previous_mae = Decimal(str(previous.mae_usdt)) if previous else pnl
        expired = now >= _aware(decision.expires_at)
        status = ShadowDecisionStatus.CLOSED if expired else ShadowDecisionStatus.TRACKING
        exit_reason = ShadowExitReason.TIME_BASED if expired else None
        evaluation = ShadowEvaluation(
            shadow_id=decision.shadow_id,
            evaluated_at=now,
            current_price=format(current_price, "f"),
            minutes_since_entry=_minutes_since(decision.created_at, now),
            unrealized_pnl_usdt=format(pnl, "f"),
            unrealized_pnl_pct=pnl_pct,
            mfe_usdt=format(max(previous_mfe, pnl), "f"),
            mae_usdt=format(min(previous_mae, pnl), "f"),
            status=status,
            exit_reason=exit_reason,
        )
        record = add_shadow_evaluation(session, evaluation)
        if expired:
            close_shadow_decision(session, decision.shadow_id, status=ShadowDecisionStatus.CLOSED)
        elif decision.status == ShadowDecisionStatus.CREATED.value:
            decision.status = ShadowDecisionStatus.TRACKING.value
        return record


def latest_prices_from_db(session: Session) -> dict[str, Decimal]:
    symbols = session.scalars(select(MarketKline.symbol).distinct()).all()
    prices: dict[str, Decimal] = {}
    for symbol in symbols:
        row = session.scalar(
            select(MarketKline)
            .where(MarketKline.symbol == symbol)
            .order_by(desc(MarketKline.close_time))
        )
        if row is not None:
            prices[symbol] = Decimal(str(row.close))
    return prices


def _minutes_since(start: datetime, end: datetime) -> float:
    return max((_aware(end) - _aware(start)).total_seconds() / 60, 0.0)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
