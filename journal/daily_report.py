from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from journal.models import DailyReport, OrderRecord, RiskDecision, StrategySignal, TradeExecution


def build_daily_report(session: Session, report_date: date, trading_mode: str) -> dict[str, object]:
    start = report_date.isoformat()
    total_signals = session.scalar(select(func.count(StrategySignal.id))) or 0
    total_orders = session.scalar(
        select(func.count(OrderRecord.id)).where(OrderRecord.trading_mode == trading_mode)
    ) or 0
    total_trades = session.scalar(select(func.count(TradeExecution.id))) or 0
    risk_rejected = session.scalar(
        select(func.count(RiskDecision.id)).where(RiskDecision.approved.is_(False))
    ) or 0
    raw = {
        "report_date": start,
        "risk_rejected_count": risk_rejected,
        "filled_count": session.scalar(
            select(func.count(OrderRecord.id)).where(OrderRecord.status == "FILLED")
        )
        or 0,
    }
    return {
        "report_date": report_date,
        "trading_mode": trading_mode,
        "total_signals": total_signals,
        "total_orders": total_orders,
        "total_trades": total_trades,
        "win_rate": 0,
        "pnl": Decimal("0"),
        "max_drawdown": Decimal("0"),
        "fees": Decimal("0"),
        "ai_summary": "Daily report placeholder: PnL integration is not enabled in MVP.",
        "raw_json": raw,
    }


def upsert_daily_report(session: Session, payload: dict[str, object]) -> DailyReport:
    report = DailyReport(**payload)
    session.add(report)
    session.flush()
    return report

