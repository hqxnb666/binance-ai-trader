from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from broker.base import Broker
from journal.models import OrderRecord, RuntimeEvent
from journal.pipeline_audit import PipelineStage, PipelineStatus, record_pipeline_stage
from orders.order_state import BINANCE_STATUS_TO_ORDER_STATE, OrderState

logger = logging.getLogger(__name__)


async def reconcile_open_orders(
    *, broker: Broker, session: Session, stale_user_stream_seconds: float = 90.0
) -> int:
    pending_statuses = {
        OrderState.ORDER_SUBMITTED.value,
        OrderState.PARTIALLY_FILLED.value,
        OrderState.FAILED.value,
        OrderState.WAITING_USER_STREAM.value,
        OrderState.RECONCILIATION_FAILED.value,
    }
    records = session.scalars(
        select(OrderRecord).where(OrderRecord.status.in_(pending_statuses))
    ).all()
    updated = 0
    for record in records:
        if not record.exchange_order_id:
            _runtime_event(
                session,
                "reconciliation_missing_exchange_order_id",
                "WARNING",
                record,
                {"client_order_id": record.client_order_id},
            )
            continue
        try:
            raw = await broker.get_order(record.symbol, record.exchange_order_id)
        except Exception:
            record.status = OrderState.RECONCILIATION_FAILED.value
            updated += 1
            _audit(session, record, "ERROR", {"error": "REST get_order failed"})
            continue
        state = BINANCE_STATUS_TO_ORDER_STATE.get(str(raw.get("status", "")))
        if state is None:
            _runtime_event(
                session,
                "reconciliation_unknown_status",
                "WARNING",
                record,
                {"raw": raw},
            )
            continue
        if state and record.status != state.value:
            old_status = record.status
            record.status = state.value
            updated += 1
            _audit(session, record, "OK", {"old_status": old_status, "rest_status": state.value})
            logger.info(
                "reconciliation_status_updated",
                extra={
                    "client_order_id": record.client_order_id,
                    "old_status": old_status,
                    "new_status": state.value,
                },
            )
        elif _is_stale_waiting_for_user_stream(record, stale_user_stream_seconds):
            _runtime_event(
                session,
                "user_stream_event_stale",
                "WARNING",
                record,
                {"status": record.status, "stale_after_seconds": stale_user_stream_seconds},
            )
            _audit(session, record, "WARNING", {"status": record.status})
    session.flush()
    logger.info("reconciliation_completed", extra={"updated": updated})
    return updated


def _is_stale_waiting_for_user_stream(record: OrderRecord, seconds: float) -> bool:
    waiting_statuses = {OrderState.WAITING_USER_STREAM.value, OrderState.PARTIALLY_FILLED.value}
    if record.status not in waiting_statuses:
        return False
    updated_at = record.updated_at
    if updated_at is None:
        return False
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    return (datetime.now(UTC) - updated_at).total_seconds() > seconds


def _runtime_event(
    session: Session,
    event_type: str,
    severity: str,
    record: OrderRecord,
    payload: dict[str, object],
) -> None:
    session.add(
        RuntimeEvent(
            source="reconciliation",
            event_type=event_type,
            severity=severity,
            message=f"{record.symbol} {record.client_order_id}",
            raw_event_json=payload,
        )
    )


def _audit(
    session: Session,
    record: OrderRecord,
    status: str,
    payload: dict[str, object],
) -> None:
    record_pipeline_stage(
        session,
        run_id=f"order-{record.client_order_id}",
        symbol=record.symbol,
        stage=PipelineStage.RECONCILED,
        status=PipelineStatus(status),
        order_record_id=record.id,
        raw_context_json=payload,
    )
