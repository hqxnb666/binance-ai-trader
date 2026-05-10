from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ai.pricing import estimate_openai_cost_usd
from journal.models import OpenAIUsageRecord

SENSITIVE_RE = re.compile(
    r"(sk-[A-Za-z0-9_\-]+|api[_-]?key[=:]\S+|secret[=:]\S+|token[=:]\S+)",
    re.IGNORECASE,
)


def record_openai_usage(
    session: Session,
    *,
    role: str,
    model: str,
    operation_name: str,
    status: str,
    request_id: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cached_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost_usd: Decimal | float | str | None = None,
    latency_ms: int | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    input_payload: dict[str, Any] | None = None,
    output_payload: dict[str, Any] | None = None,
) -> OpenAIUsageRecord:
    if estimated_cost_usd is None:
        estimated_cost = estimate_openai_cost_usd(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
        )
    else:
        estimated_cost = Decimal(str(estimated_cost_usd))
    record = OpenAIUsageRecord(
        role=role,
        model=model,
        operation_name=operation_name,
        request_id=request_id,
        status=status,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost,
        latency_ms=latency_ms,
        error_type=error_type,
        error_message_sanitized=sanitize_error(error_message),
        input_hash=_hash_json(input_payload) if input_payload is not None else None,
        output_hash=_hash_json(output_payload) if output_payload is not None else None,
    )
    session.add(record)
    session.flush()
    return record


def get_today_openai_cost(session: Session) -> Decimal:
    start = _utc_day_start()
    return _sum_cost_since(session, start)


def get_month_openai_cost(session: Session) -> Decimal:
    now = datetime.now(UTC)
    start = datetime(now.year, now.month, 1, tzinfo=UTC)
    return _sum_cost_since(session, start)


def get_role_call_count_today(session: Session, role: str) -> int:
    start = _utc_day_start()
    return int(
        session.scalar(
            select(func.count(OpenAIUsageRecord.id))
            .where(OpenAIUsageRecord.created_at >= start)
            .where(OpenAIUsageRecord.role == str(role))
            .where(OpenAIUsageRecord.status.in_(["SUCCESS", "FAILED", "SKIPPED_BUDGET"]))
        )
        or 0
    )


def list_recent_openai_usage(session: Session, limit: int = 50) -> list[OpenAIUsageRecord]:
    return session.scalars(
        select(OpenAIUsageRecord)
        .order_by(desc(OpenAIUsageRecord.created_at))
        .limit(limit)
    ).all()


def summarize_openai_usage(session: Session, *, days: int = 1) -> dict[str, Any]:
    since = datetime.now(UTC) - timedelta(days=max(days, 1))
    rows = session.scalars(
        select(OpenAIUsageRecord).where(OpenAIUsageRecord.created_at >= since)
    ).all()
    by_role: dict[str, dict[str, Any]] = {}
    by_model: dict[str, dict[str, Any]] = {}
    total_cost = Decimal("0")
    for row in rows:
        cost = Decimal(row.estimated_cost_usd or 0)
        total_cost += cost
        _accumulate(by_role, row.role, cost, row.status)
        _accumulate(by_model, row.model, cost, row.status)
    return {
        "days": days,
        "total_calls": len(rows),
        "estimated_cost_usd": float(total_cost),
        "by_role": by_role,
        "by_model": by_model,
    }


def sanitize_error(message: str | None) -> str | None:
    if not message:
        return None
    return SENSITIVE_RE.sub("[REDACTED]", message)[:1000]


def _sum_cost_since(session: Session, start: datetime) -> Decimal:
    value = session.scalar(
        select(func.coalesce(func.sum(OpenAIUsageRecord.estimated_cost_usd), 0)).where(
            OpenAIUsageRecord.created_at >= start
        )
    )
    return Decimal(value or 0)


def _utc_day_start() -> datetime:
    now = datetime.now(UTC)
    return datetime(now.year, now.month, now.day, tzinfo=UTC)


def _hash_json(payload: dict[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _accumulate(target: dict[str, dict[str, Any]], key: str, cost: Decimal, status: str) -> None:
    bucket = target.setdefault(
        key,
        {"calls": 0, "estimated_cost_usd": 0.0, "success": 0, "failed": 0, "skipped_budget": 0},
    )
    bucket["calls"] += 1
    bucket["estimated_cost_usd"] = float(Decimal(str(bucket["estimated_cost_usd"])) + cost)
    if status == "SUCCESS":
        bucket["success"] += 1
    elif status == "SKIPPED_BUDGET":
        bucket["skipped_budget"] += 1
    else:
        bucket["failed"] += 1
