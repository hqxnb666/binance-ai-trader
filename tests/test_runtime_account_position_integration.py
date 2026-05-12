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
        raise AssertionError("real broker call is not expected")

    async def cancel_order(self, symbol, order_id):
        return {}

    async def get_order(self, symbol, order_id):
        return {}


def _factory():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)


def test_runtime_health_contains_account_position_status() -> None:
    daemon = TradingDaemon(
        settings=load_settings(),
        session_factory=_factory(),
        broker=FakeBroker(),
    )
    health = daemon.health().model_dump(mode="json")
    assert "account_position_status" in health
    assert health["account_position_status"]["account_source"] == "simulated_default"


def test_runtime_data_quality_uses_current_last_kline_time() -> None:
    daemon = TradingDaemon(
        settings=load_settings(),
        session_factory=_factory(),
        broker=FakeBroker(),
    )
    daemon.last_rest_poll_ok_at = datetime.now(UTC)
    daemon.last_kline_time = datetime.now(UTC)
    snapshot = daemon._evaluate_data_quality_runtime(active_strategy_plan=None)
    assert snapshot.last_kline_time is not None
    assert "KLINE_STALENESS:LATEST_KLINE_TIMESTAMP_IS_MISSING" not in snapshot.reason_codes


@pytest.mark.asyncio
async def test_risk_uses_latest_account_state_not_only_hardcoded_1000() -> None:
    factory = _factory()
    daemon = TradingDaemon(settings=load_settings(), session_factory=factory, broker=FakeBroker())
    daemon.exchange_filters["BTCUSDT"] = SymbolFilters(
        "BTCUSDT",
        Decimal("0.1"),
        Decimal("0.001"),
        Decimal("0.001"),
        Decimal("10"),
    )
    daemon.latest_account_state = _account_state(Decimal("2000"))
    daemon.latest_position_states["BTCUSDT"] = _position_state()
    daemon.last_rest_poll_ok_at = datetime.now(UTC)
    daemon.last_kline_time = datetime.now(UTC)
    with factory() as session:
        signal_record = StrategySignal(**_signal().model_dump())
        ai_record = AIAnalysis(
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
        session.add_all([signal_record, ai_record])
        session.flush()
        await daemon._risk_and_order(
            session=session,
            symbol="BTCUSDT",
            signal=_signal(),
            signal_record=signal_record,
            ai_result=_ai_result(),
            ai_record=ai_record,
            snapshot={"symbol": "BTCUSDT", "price": 100, "atr14_5m": 1},
            run_id="account-state-test",
        )
        risk = session.query(RiskDecision).order_by(RiskDecision.id.desc()).first()
    assert risk is not None
    assert risk.risk_state_json["account"]["equity_usdt"] == "2000"


@pytest.mark.asyncio
async def test_real_order_path_unknown_account_is_blocked_by_data_quality() -> None:
    settings = load_settings().model_copy(
        update={
            "trading_dry_run": False,
            "order_execution_enabled": True,
            "risk_config": load_settings().risk_config.model_copy(
                update={"block_on_ws_disconnect": False}
            ),
        }
    )
    factory = _factory()
    daemon = TradingDaemon(settings=settings, session_factory=factory, broker=FakeBroker())
    daemon.exchange_filters["BTCUSDT"] = SymbolFilters(
        "BTCUSDT",
        Decimal("0.1"),
        Decimal("0.001"),
        Decimal("0.001"),
        Decimal("10"),
    )
    daemon.latest_account_state = None
    daemon.latest_position_states = {}
    daemon.last_rest_poll_ok_at = datetime.now(UTC)
    daemon.last_kline_time = datetime.now(UTC)
    daemon._user_connected = lambda: True  # type: ignore[method-assign]
    with factory() as session:
        signal_record = StrategySignal(**_signal().model_dump())
        ai_record = AIAnalysis(
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
        session.add_all([signal_record, ai_record])
        session.flush()
        await daemon._risk_and_order(
            session=session,
            symbol="BTCUSDT",
            signal=_signal(),
            signal_record=signal_record,
            ai_result=_ai_result(),
            ai_record=ai_record,
            snapshot={"symbol": "BTCUSDT", "price": 100, "atr14_5m": 1},
            run_id="dq-block-test",
        )
    assert daemon.latest_data_quality_snapshot is not None
    assert daemon.latest_data_quality_snapshot.safe_for_order is False


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
