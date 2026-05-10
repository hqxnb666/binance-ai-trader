from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ai.strategy_schemas import StrategyPlan, StrategyPlanUpdate
from journal.models import StrategyPlanRecord

SENSITIVE_MARKERS = ("KEY", "SECRET", "TOKEN", "PASSWORD")


def save_strategy_plan(
    session: Session,
    *,
    plan: StrategyPlan | StrategyPlanUpdate,
    raw_input_json: dict[str, Any],
    model: str,
    status: str = "ACTIVE",
) -> StrategyPlanRecord:
    output_json = plan.model_dump(mode="json")
    input_json = sanitize_json(raw_input_json)
    expires_at = output_json.get("expires_at") or output_json.get("new_expiration_time")
    expires_at_dt = datetime.fromisoformat(expires_at) if isinstance(expires_at, str) else None
    if expires_at_dt and expires_at_dt.tzinfo is None:
        expires_at_dt = expires_at_dt.replace(tzinfo=UTC)
    if status == "ACTIVE":
        _supersede_active_plans(session)
    record = StrategyPlanRecord(
        expires_at=expires_at_dt,
        planning_mode=str(output_json.get("planning_mode", "")),
        plan_action=str(output_json.get("plan_action", "")),
        model=model,
        schema_version=str(output_json.get("schema_version", "")),
        status=status,
        market_regime=output_json.get("market_regime"),
        trade_bias=output_json.get("trade_bias"),
        risk_mode=output_json.get("risk_mode"),
        max_position_pct=output_json.get("max_position_pct"),
        confidence=float(output_json.get("confidence", 0)),
        requires_human_review=bool(output_json.get("requires_human_review", True)),
        symbol_scope_json=list(output_json.get("symbol_scope", [])),
        allowed_actions_json=list(output_json.get("allowed_actions", [])),
        blocked_actions_json=list(output_json.get("blocked_actions", [])),
        symbol_permissions_json=_permission_rules_to_dict(output_json.get("symbol_permissions")),
        invalidation_conditions_json=list(output_json.get("invalidation_conditions", [])),
        reason_codes_json=list(output_json.get("reason_codes", [])),
        explanation=str(output_json.get("explanation", "")),
        input_hash=_hash_json(input_json),
        output_hash=_hash_json(output_json),
        raw_input_json=input_json,
        raw_output_json=output_json,
    )
    session.add(record)
    session.flush()
    return record


def get_active_strategy_plan(session: Session) -> StrategyPlanRecord | None:
    now = datetime.now(UTC)
    return session.scalar(
        select(StrategyPlanRecord)
        .where(StrategyPlanRecord.status == "ACTIVE")
        .where(
            (StrategyPlanRecord.expires_at.is_(None))
            | (StrategyPlanRecord.expires_at > now)
        )
        .order_by(desc(StrategyPlanRecord.created_at))
    )


def expire_strategy_plan(session: Session, plan_id: int) -> StrategyPlanRecord | None:
    record = session.get(StrategyPlanRecord, plan_id)
    if record is not None:
        record.status = "EXPIRED"
        session.flush()
    return record


def list_recent_strategy_plans(session: Session, limit: int = 20) -> list[StrategyPlanRecord]:
    return session.scalars(
        select(StrategyPlanRecord).order_by(desc(StrategyPlanRecord.created_at)).limit(limit)
    ).all()


def sanitize_json(payload: Any) -> Any:
    if isinstance(payload, dict):
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            if any(marker in key.upper() for marker in SENSITIVE_MARKERS):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = sanitize_json(value)
        return sanitized
    if isinstance(payload, list):
        return [sanitize_json(item) for item in payload[:50]]
    return payload


def _supersede_active_plans(session: Session) -> None:
    for record in session.scalars(
        select(StrategyPlanRecord).where(StrategyPlanRecord.status == "ACTIVE")
    ):
        record.status = "SUPERSEDED"


def _hash_json(payload: dict[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _permission_rules_to_dict(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(symbol).upper(): str(permission) for symbol, permission in value.items()}
    if isinstance(value, list):
        result: dict[str, str] = {}
        for item in value:
            if not isinstance(item, dict):
                continue
            symbol = item.get("symbol")
            permission = item.get("permission")
            if symbol and permission:
                result[str(symbol).upper()] = str(permission)
        return result
    return {}
