from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from journal import models


class TradeLogger:
    def __init__(self, session: Session):
        self.session = session

    def log_strategy_signal(self, payload: dict[str, Any]) -> models.StrategySignal:
        record = models.StrategySignal(**payload)
        self.session.add(record)
        self.session.flush()
        return record

    def log_ai_analysis(self, payload: dict[str, Any]) -> models.AIAnalysis:
        record = models.AIAnalysis(**payload)
        self.session.add(record)
        self.session.flush()
        return record

    def log_risk_decision(self, payload: dict[str, Any]) -> models.RiskDecision:
        record = models.RiskDecision(**payload)
        self.session.add(record)
        self.session.flush()
        return record

    def log_order(self, payload: dict[str, Any]) -> models.OrderRecord:
        record = models.OrderRecord(**payload)
        self.session.add(record)
        self.session.flush()
        return record

    def log_execution(self, payload: dict[str, Any]) -> models.TradeExecution:
        record = models.TradeExecution(**payload)
        self.session.add(record)
        self.session.flush()
        return record

    def log_trade_review(self, payload: dict[str, Any]) -> models.TradeReview:
        record = models.TradeReview(**payload)
        self.session.add(record)
        self.session.flush()
        return record

    def log_runtime_event(self, payload: dict[str, Any]) -> models.RuntimeEvent:
        record = models.RuntimeEvent(**payload)
        self.session.add(record)
        self.session.flush()
        return record

    def log_pipeline_audit(self, payload: dict[str, Any]) -> models.PipelineAudit:
        record = models.PipelineAudit(**payload)
        self.session.add(record)
        self.session.flush()
        return record


    def log_daily_report(self, payload: dict[str, Any]) -> models.DailyReport:
        record = models.DailyReport(**payload)
        self.session.add(record)
        self.session.flush()
        return record

    def log_rejection(
        self,
        *,
        symbol: str,
        reason: str,
        state: dict[str, Any],
        signal_id: int | None = None,
        ai_analysis_id: int | None = None,
    ) -> models.RiskDecision:
        return self.log_risk_decision(
            {
                "symbol": symbol,
                "signal_id": signal_id,
                "ai_analysis_id": ai_analysis_id,
                "approved": False,
                "reason": reason,
                "risk_state_json": state,
            }
        )


def decimal_to_str(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")
