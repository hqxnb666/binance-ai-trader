from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from account.schemas import AccountSyncStatus, RuntimeAccountState, RuntimePositionState
from ai.schemas import SignalReview
from ai.signal_reviewer import SignalReviewResult
from binance_client.exchange_info import SymbolFilters
from broker.base import Broker
from config.settings import load_settings
from journal.models import AIAnalysis, Base, RiskDecision, StrategySignal
from risk.circuit_breaker import CircuitBreaker
from runtime.trading_daemon import TestnetTradingDaemon as TradingDaemon
from strategies.base import StrategySignalPayload


class FakeBroker(Broker):
    async def get_account(self):
        return {}

    async def get_exchange_info(self):
        return {}

    async def get_klines(self, symbol, interval, limit):
        return []

    async def place_order(self, order_request):
        raise AssertionError("kill switch must block before OrderManager/broker")

    async def cancel_order(self, symbol, order_id):
        return {}

    async def get_order(self, symbol, order_id):
        return {}


def _factory():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)


@pytest.mark.asyncio
async def test_runtime_db_kill_switch_rejects_before_order_manager() -> None:
    factory = _factory()
    daemon = TradingDaemon(settings=load_settings(), session_factory=factory, broker=FakeBroker())
    daemon.exchange_filters["BTCUSDT"] = SymbolFilters(
        "BTCUSDT",
        Decimal("0.1"),
        Decimal("0.001"),
        Decimal("0.001"),
        Decimal("10"),
    )
    daemon.latest_account_state = _account_state(Decimal("1000"))
    daemon.latest_position_states["BTCUSDT"] = _position_state()
    daemon.last_rest_poll_ok_at = datetime.now(UTC)
    daemon.last_kline_time = datetime.now(UTC)
    with factory() as session:
        CircuitBreaker(session).set_enabled(True)
        signal = StrategySignal(**_signal().model_dump())
        ai = AIAnalysis(
            symbol="BTCUSDT",
            analysis_type="signal_review",
            model="test",
            prompt_version="test",
            input_json={},
            output_json={},
            schema_valid=True,
            decision="APPROVE_TO_RISK_ENGINE",
            confidence=0.9,
            risk_level="low",
        )
        session.add_all([signal, ai])
        session.flush()
        await daemon._risk_and_order(
            session=session,
            symbol="BTCUSDT",
            signal=_signal(),
            signal_record=signal,
            ai_result=_ai_result(),
            ai_record=ai,
            snapshot={"symbol": "BTCUSDT", "price": 100, "atr14_5m": 1},
            run_id="kill-switch-test",
        )
        decisions = session.query(RiskDecision).all()
    assert decisions[-1].approved is False
    assert decisions[-1].reason == "runtime kill switch enabled"


def test_runtime_health_reports_kill_switch_state() -> None:
    factory = _factory()
    daemon = TradingDaemon(settings=load_settings(), session_factory=factory, broker=FakeBroker())
    with factory() as session:
        CircuitBreaker(session).set_enabled(True)
        session.commit()
    health = daemon.health().model_dump(mode="json")
    assert health["kill_switch_state"]["runtime_enabled"] is True
    assert health["risk_runtime_status"]["risk_engine_reused"] is True


def _signal() -> StrategySignalPayload:
    return StrategySignalPayload(
        symbol="BTCUSDT",
        strategy_name="ema_trend",
        strategy_version="v1.0",
        timeframe="5m",
        side="BUY",
        signal_type="TEST",
        confidence=0.8,
        reason="test",
        raw_payload_json={},
    )


def _review() -> SignalReview:
    return SignalReview.model_validate(
        {
            "decision": "APPROVE_TO_RISK_ENGINE",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "confidence": 0.9,
            "risk_level": "low",
            "market_regime": "trend_up",
            "reason": "ok",
            "warnings": [],
            "max_position_pct": 1,
            "requires_human_review": False,
        }
    )


def _ai_result() -> SignalReviewResult:
    return SignalReviewResult(
        review=_review(),
        approved_for_risk=True,
        reason="ok",
        schema_valid=True,
        actual_model="test",
        input_payload={},
    )


def _account_state(equity: Decimal) -> RuntimeAccountState:
    return RuntimeAccountState(
        created_at=datetime.now(UTC),
        status=AccountSyncStatus.OK,
        source="binance_rest",
        equity_usdt=equity,
        available_usdt=equity,
        balances=[],
        daily_realized_pnl="unknown",
        daily_unrealized_pnl="unknown",
        is_safe_for_real_order=True,
    )


def _position_state() -> RuntimePositionState:
    return RuntimePositionState(
        created_at=datetime.now(UTC),
        symbol="BTCUSDT",
        status="OK",
        source="binance_rest",
        base_asset="BTC",
        quote_asset="USDT",
        quantity=0,
        available_quantity=0,
        locked_quantity=0,
        estimated_value_usdt=0,
        position_pct=0,
        side="FLAT",
        is_safe_for_real_order=True,
    )
