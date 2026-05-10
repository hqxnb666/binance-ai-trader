from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from binance_client.errors import RiskRejectedError
from broker.base import Broker, OrderRequest, OrderResult
from journal.models import OrderRecord, RiskDecision, RuntimeEvent, TradeExecution
from orders.order_state import BINANCE_STATUS_TO_ORDER_STATE, OrderState
from strategies.base import StrategySignalPayload

logger = logging.getLogger(__name__)


class OrderManager:
    def __init__(self, *, broker: Broker, session: Session, trading_mode: str):
        self.broker = broker
        self.session = session
        self.trading_mode = trading_mode

    async def submit_order(
        self,
        *,
        signal: StrategySignalPayload,
        risk_decision: RiskDecision,
        order_request: OrderRequest,
        ai_analysis_id: int | None = None,
        dry_run: bool = False,
        order_execution_enabled: bool = True,
        precheck_test_order: bool = False,
    ) -> OrderRecord:
        client_order_id = order_request.client_order_id or generate_client_order_id(
            self.trading_mode
        )
        request = order_request.model_copy(update={"client_order_id": client_order_id})
        if dry_run or not order_execution_enabled:
            status = (
                OrderState.DRY_RUN_APPROVED
                if risk_decision.approved
                else OrderState.DRY_RUN_REJECTED
            )
            record = self._create_order_record(
                signal=signal,
                request=request,
                status=status,
                ai_analysis_id=ai_analysis_id,
                risk_decision_id=risk_decision.id,
            )
            self.session.flush()
            logger.info(
                "dry_run_order_created",
                extra={
                    "symbol": request.symbol,
                    "client_order_id": client_order_id,
                    "approved": risk_decision.approved,
                },
            )
            return record
        if not risk_decision.approved:
            record = self._create_order_record(
                signal=signal,
                request=request,
                status=OrderState.RISK_REJECTED,
                ai_analysis_id=ai_analysis_id,
                risk_decision_id=risk_decision.id,
            )
            self.session.flush()
            raise RiskRejectedError(risk_decision.reason)
        try:
            if precheck_test_order:
                logger.info(
                    "test_order_submitted",
                    extra={"symbol": request.symbol, "client_order_id": client_order_id},
                )
                await self.broker.test_order(request)
            result = await self.broker.place_order(request)
        except Exception:
            self._create_order_record(
                signal=signal,
                request=request,
                status=OrderState.FAILED,
                ai_analysis_id=ai_analysis_id,
                risk_decision_id=risk_decision.id,
            )
            self.session.flush()
            raise
        status = BINANCE_STATUS_TO_ORDER_STATE.get(result.status, OrderState.WAITING_USER_STREAM)
        record = self._create_order_record(
            signal=signal,
            request=request,
            status=status,
            ai_analysis_id=ai_analysis_id,
            risk_decision_id=risk_decision.id,
            result=result,
        )
        self.session.flush()
        logger.info(
            "order_submitted",
            extra={"symbol": request.symbol, "client_order_id": client_order_id},
        )
        return record

    def _create_order_record(
        self,
        *,
        signal: StrategySignalPayload,
        request: OrderRequest,
        status: OrderState,
        ai_analysis_id: int | None,
        risk_decision_id: int | None,
        result: OrderResult | None = None,
    ) -> OrderRecord:
        exchange_order_id = str(result.order_id) if result and result.order_id is not None else None
        record = OrderRecord(
            exchange_order_id=exchange_order_id,
            client_order_id=request.client_order_id or generate_client_order_id(self.trading_mode),
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            price=request.price,
            quantity=request.quantity,
            status=status.value,
            trading_mode=self.trading_mode,
            strategy_name=signal.strategy_name,
            strategy_version=signal.strategy_version,
            ai_analysis_id=ai_analysis_id,
            risk_decision_id=risk_decision_id,
        )
        self.session.add(record)
        return record

    def handle_user_stream_event(self, event: dict[str, Any]) -> OrderRecord | None:
        event_type = str(event.get("e", "unknown"))
        logger.info("user_stream_event_received", extra={"event_type": event_type})
        if event_type == "executionReport":
            return self.handle_execution_report(event)
        if event_type in {"outboundAccountPosition", "balanceUpdate"}:
            self._log_runtime_event(event, severity="INFO", message="account event")
            return None
        self._log_runtime_event(event, severity="WARNING", message="unknown user stream event")
        logger.warning("unknown_user_stream_event", extra={"event_type": event_type})
        return None

    def handle_execution_report(self, event: dict[str, Any]) -> OrderRecord | None:
        self._log_runtime_event(event, severity="INFO", message="execution report")
        client_order_id = event.get("c")
        if not client_order_id:
            self._log_runtime_event(
                event, severity="WARNING", message="executionReport without client_order_id"
            )
            return None
        record = self.session.scalar(
            select(OrderRecord).where(OrderRecord.client_order_id == str(client_order_id))
        )
        if record is None:
            self._log_runtime_event(
                event, severity="WARNING", message="executionReport for unknown local order"
            )
            logger.warning(
                "execution_report_unknown_order",
                extra={"client_order_id": str(client_order_id)},
            )
            return None
        exchange_status = str(event.get("X", ""))
        record.status = BINANCE_STATUS_TO_ORDER_STATE.get(exchange_status, OrderState.FAILED).value
        if event.get("i") is not None:
            record.exchange_order_id = str(event["i"])
        if event.get("x") == "TRADE" and Decimal(str(event.get("l", "0"))) > 0:
            execution = TradeExecution(
                order_record_id=record.id,
                symbol=str(event.get("s", record.symbol)),
                side=str(event.get("S", record.side)),
                price=Decimal(str(event.get("L", "0"))),
                quantity=Decimal(str(event.get("l", "0"))),
                commission=Decimal(str(event.get("n", "0"))),
                commission_asset=event.get("N"),
                event_time=datetime.fromtimestamp(int(event.get("E", 0)) / 1000, tz=UTC),
                raw_event_json=event,
            )
            self.session.add(execution)
        self.session.flush()
        logger.info(
            "order_status_updated",
            extra={"client_order_id": str(client_order_id), "status": record.status},
        )
        return record

    def _log_runtime_event(
        self, event: dict[str, Any], *, severity: str, message: str
    ) -> RuntimeEvent:
        record = RuntimeEvent(
            source="user_stream",
            event_type=str(event.get("e", "unknown")),
            severity=severity,
            message=message,
            raw_event_json=event,
        )
        self.session.add(record)
        self.session.flush()
        return record


def generate_client_order_id(trading_mode: str) -> str:
    prefix = "btai-t" if trading_mode == "testnet" else "btai-l"
    return f"{prefix}-{uuid.uuid4().hex[:20]}"
