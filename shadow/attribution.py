from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from config.settings import Settings
from journal.models import ShadowAttributionRecord
from journal.strategy_plan_store import sanitize_json

ATTRIBUTION_SUMMARY_KEYS = (
    "local_candidate_count",
    "local_no_signal_count",
    "strategy_plan_blocked_real_order_count",
    "strategy_plan_no_trade_count",
    "strategy_plan_human_review_count",
    "ai_approved_count",
    "ai_human_review_count",
    "ai_rejected_count",
    "risk_approved_count",
    "risk_rejected_count",
    "risk_symbol_position_limit_count",
    "risk_total_position_limit_count",
    "would_place_order_shadow_count",
    "would_place_order_real_path_count",
)


class ShadowAttributionRecorder:
    """Records read-only layer attribution for Shadow Mode diagnostics."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def enabled(self) -> bool:
        return self.settings.enable_shadow_mode and self.settings.shadow_attribution_enabled

    def record(
        self,
        session: Session,
        *,
        symbol: str,
        side: str = "HOLD",
        local_strategy: dict[str, Any] | None = None,
        data_quality_gate: dict[str, Any] | None = None,
        strategy_plan_gate: dict[str, Any] | None = None,
        ai_review: dict[str, Any] | None = None,
        risk_engine: dict[str, Any] | None = None,
        final_real_order_path: dict[str, Any] | None = None,
        shadow_observation: dict[str, Any] | None = None,
    ) -> ShadowAttributionRecord | None:
        if not self.enabled():
            return None
        local_strategy = local_strategy or {}
        data_quality_gate = data_quality_gate or {}
        strategy_plan_gate = strategy_plan_gate or {}
        ai_review = ai_review or {}
        risk_engine = risk_engine or {}
        final_real_order_path = final_real_order_path or {}
        shadow_observation = shadow_observation or {}
        record = ShadowAttributionRecord(
            symbol=symbol.upper(),
            side=str(side or local_strategy.get("side") or "HOLD").upper(),
            local_has_candidate=bool(local_strategy.get("has_candidate")),
            local_confidence=_float_or_none(local_strategy.get("confidence")),
            local_reason=_str_or_none(local_strategy.get("reason"), 500),
            data_quality_status=_str_or_none(data_quality_gate.get("status"), 30),
            data_quality_safe_for_signal_review=bool(
                data_quality_gate.get("safe_for_signal_review")
            ),
            data_quality_safe_for_order=bool(data_quality_gate.get("safe_for_order")),
            data_quality_blocking_reasons_json=_str_list(
                data_quality_gate.get("blocking_reasons")
            ),
            active_strategy_plan_id=_str_or_none(strategy_plan_gate.get("active_plan_id")),
            strategy_plan_risk_mode=_str_or_none(strategy_plan_gate.get("risk_mode"), 30),
            strategy_plan_trade_bias=_str_or_none(strategy_plan_gate.get("trade_bias"), 30),
            strategy_plan_requires_human_review=bool(
                strategy_plan_gate.get("requires_human_review")
            ),
            strategy_plan_allowed_actions_json=_str_list(
                strategy_plan_gate.get("allowed_actions")
            ),
            strategy_plan_symbol_permission=_str_or_none(
                strategy_plan_gate.get("symbol_permission"), 30
            ),
            strategy_plan_blocks_real_order=bool(
                strategy_plan_gate.get("blocks_real_order")
            ),
            strategy_plan_blocks_shadow_evaluation=bool(
                strategy_plan_gate.get("blocks_shadow_evaluation")
            ),
            ai_decision=_str_or_none(ai_review.get("decision"), 50),
            ai_requires_human_review=_bool_or_none(ai_review.get("requires_human_review")),
            ai_schema_valid=_bool_or_none(ai_review.get("schema_valid")),
            risk_approved=_bool_or_none(risk_engine.get("approved")),
            risk_reason=_str_or_none(risk_engine.get("reason"), 500),
            evaluated_with_account_profile=_str_or_none(
                risk_engine.get("evaluated_with_account_profile"), 50
            ),
            would_submit_real_order=bool(final_real_order_path.get("would_submit_real_order")),
            final_blocked_by=str(
                final_real_order_path.get("blocked_by")
                or shadow_observation.get("primary_blocker")
                or "UNKNOWN"
            )[:80],
            candidate_observed=bool(shadow_observation.get("candidate_observed")),
            stage_reached=str(shadow_observation.get("stage_reached") or "LOCAL_SIGNAL")[:50],
            primary_blocker=str(shadow_observation.get("primary_blocker") or "UNKNOWN")[:50],
            notes_json=_str_list(shadow_observation.get("notes"), limit=20),
            raw_context_json=_sanitize(
                {
                    "local_strategy": local_strategy,
                    "data_quality_gate": data_quality_gate,
                    "strategy_plan_gate": strategy_plan_gate,
                    "ai_review": ai_review,
                    "risk_engine": risk_engine,
                    "final_real_order_path": final_real_order_path,
                    "shadow_observation": shadow_observation,
                }
            ),
        )
        session.add(record)
        session.flush()
        return record


def list_recent_shadow_attributions(
    session: Session,
    *,
    limit: int = 100,
) -> list[ShadowAttributionRecord]:
    return session.scalars(
        select(ShadowAttributionRecord)
        .order_by(desc(ShadowAttributionRecord.created_at))
        .limit(limit)
    ).all()


def build_shadow_attribution_summary(
    session: Session,
    *,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    hours: int = 24,
) -> dict[str, int]:
    end = window_end or datetime.now(UTC)
    start = window_start or end - timedelta(hours=hours)
    rows = session.scalars(
        select(ShadowAttributionRecord)
        .where(ShadowAttributionRecord.created_at >= start)
        .where(ShadowAttributionRecord.created_at <= end)
    ).all()
    return summarize_shadow_attributions(rows)


def summarize_shadow_attributions(rows: list[ShadowAttributionRecord]) -> dict[str, int]:
    counts = {key: 0 for key in ATTRIBUTION_SUMMARY_KEYS}
    for row in rows:
        if row.local_has_candidate:
            counts["local_candidate_count"] += 1
        else:
            counts["local_no_signal_count"] += 1
        if row.strategy_plan_blocks_real_order:
            counts["strategy_plan_blocked_real_order_count"] += 1
        if row.strategy_plan_risk_mode == "no_trade" or row.strategy_plan_trade_bias == "no_trade":
            counts["strategy_plan_no_trade_count"] += 1
        if row.strategy_plan_requires_human_review:
            counts["strategy_plan_human_review_count"] += 1
        if str(row.ai_decision or "").upper() == "APPROVE_TO_RISK_ENGINE":
            counts["ai_approved_count"] += 1
        if (
            str(row.ai_decision or "").upper() == "HUMAN_REVIEW_REQUIRED"
            or row.ai_requires_human_review
        ):
            counts["ai_human_review_count"] += 1
        if str(row.ai_decision or "").upper() == "REJECT_SIGNAL":
            counts["ai_rejected_count"] += 1
        if row.risk_approved is True:
            counts["risk_approved_count"] += 1
        if row.risk_approved is False:
            counts["risk_rejected_count"] += 1
        reason = str(row.risk_reason or "").lower()
        if "symbol position limit" in reason:
            counts["risk_symbol_position_limit_count"] += 1
        if "total position limit" in reason:
            counts["risk_total_position_limit_count"] += 1
        if row.final_blocked_by == "WOULD_PLACE_ORDER_SHADOW_ONLY":
            counts["would_place_order_shadow_count"] += 1
        if row.final_blocked_by == "WOULD_PLACE_ORDER_REAL_PATH" or row.would_submit_real_order:
            counts["would_place_order_real_path_count"] += 1
    return counts


def primary_blocking_layer(summary: dict[str, int]) -> str:
    if not summary or not any(summary.values()):
        return "NO_SAMPLES"
    candidates = {
        "LOCAL_STRATEGY": summary.get("local_no_signal_count", 0),
        "STRATEGY_PLAN": summary.get("strategy_plan_blocked_real_order_count", 0),
        "AI_REVIEW": summary.get("ai_human_review_count", 0)
        + summary.get("ai_rejected_count", 0),
        "RISK_ENGINE": summary.get("risk_rejected_count", 0),
        "DATA_QUALITY": 0,
    }
    layer, count = max(candidates.items(), key=lambda item: item[1])
    if count <= 0 and summary.get("would_place_order_shadow_count", 0) > 0:
        return "NONE"
    return layer if count > 0 else "NO_SAMPLES"


def shadow_attribution_human_summary(summary: dict[str, int]) -> list[str]:
    layer = primary_blocking_layer(summary)
    lines: list[str] = []
    local = summary.get("local_candidate_count", 0)
    if local:
        lines.append(f"Local EMA produced {local} candidate signals in the attribution window.")
    else:
        lines.append("No local EMA candidate signals were observed in the attribution window.")
    if summary.get("strategy_plan_blocked_real_order_count", 0):
        lines.append("Local candidates exist, but StrategyPlan blocks the real order path.")
    if summary.get("risk_rejected_count", 0):
        lines.append(
            f"RiskEngine rejected {summary['risk_rejected_count']} attribution samples."
        )
    if summary.get("would_place_order_shadow_count", 0):
        lines.append(
            f"{summary['would_place_order_shadow_count']} samples reached shadow would-place-order."
        )
    lines.append(f"Primary blocking layer: {layer}.")
    return lines


def shadow_attribution_to_dict(record: ShadowAttributionRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "created_at": record.created_at.isoformat(),
        "symbol": record.symbol,
        "side": record.side,
        "local_strategy": {
            "has_candidate": record.local_has_candidate,
            "side": record.side,
            "confidence": float(record.local_confidence)
            if record.local_confidence is not None
            else None,
            "reason": record.local_reason,
        },
        "data_quality_gate": {
            "status": record.data_quality_status,
            "safe_for_signal_review": record.data_quality_safe_for_signal_review,
            "safe_for_order": record.data_quality_safe_for_order,
            "blocking_reasons": record.data_quality_blocking_reasons_json,
        },
        "strategy_plan_gate": {
            "active_plan_id": record.active_strategy_plan_id,
            "risk_mode": record.strategy_plan_risk_mode,
            "trade_bias": record.strategy_plan_trade_bias,
            "requires_human_review": record.strategy_plan_requires_human_review,
            "allowed_actions": record.strategy_plan_allowed_actions_json,
            "symbol_permission": record.strategy_plan_symbol_permission,
            "blocks_real_order": record.strategy_plan_blocks_real_order,
            "blocks_shadow_evaluation": record.strategy_plan_blocks_shadow_evaluation,
        },
        "ai_review": {
            "decision": record.ai_decision or "NOT_RUN",
            "requires_human_review": record.ai_requires_human_review,
            "schema_valid": record.ai_schema_valid,
        },
        "risk_engine": {
            "approved": record.risk_approved,
            "reason": record.risk_reason,
            "evaluated_with_account_profile": record.evaluated_with_account_profile,
        },
        "final_real_order_path": {
            "would_submit_real_order": record.would_submit_real_order,
            "blocked_by": record.final_blocked_by,
        },
        "shadow_observation": {
            "candidate_observed": record.candidate_observed,
            "stage_reached": record.stage_reached,
            "primary_blocker": record.primary_blocker,
            "notes": record.notes_json,
        },
    }


def top_attribution_reasons(
    rows: list[ShadowAttributionRecord],
    limit: int = 10,
) -> list[dict[str, Any]]:
    counter = Counter(row.final_blocked_by for row in rows)
    return [
        {"reason": reason, "count": count}
        for reason, count in counter.most_common(limit)
    ]


def _sanitize(value: Any) -> Any:
    return sanitize_json(value)


def _str_or_none(value: Any, limit: int = 100) -> str | None:
    if value is None:
        return None
    return str(value)[:limit]


def _str_list(value: Any, *, limit: int = 20) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item)[:300] for item in value[:limit]]
    return [str(value)[:300]]


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)
