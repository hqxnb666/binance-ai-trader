from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from ai.schemas import SignalReview
from binance_client.exchange_info import SymbolFilters
from binance_client.market_stream import StreamHealth
from config.settings import load_settings
from risk.risk_engine import AccountState, MarketHealth, PositionState, RiskEngine
from strategies.base import StrategySignalPayload


def test_stream_health_marks_stale_stream_unhealthy() -> None:
    health = StreamHealth(connected=True, unhealthy_after_seconds=3)
    health.last_message_time = datetime.now(UTC) - timedelta(seconds=10)
    assert health.is_healthy() is False
    assert health.as_dict()["reconnect_count"] == 0


def test_risk_rejects_reconnecting_websocket() -> None:
    settings = load_settings()
    signal = StrategySignalPayload(
        symbol="BTCUSDT",
        strategy_name="ema_trend",
        strategy_version="v1.0",
        timeframe="5m",
        side="BUY",
        signal_type="ENTRY_CANDIDATE",
        confidence=0.7,
        reason="test",
        raw_payload_json={},
    )
    review = SignalReview.model_validate(
        {
            "decision": "APPROVE_TO_RISK_ENGINE",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "confidence": 0.8,
            "risk_level": "low",
            "market_regime": "trend_up",
            "reason": "ok",
            "warnings": [],
            "max_position_pct": 5,
            "requires_human_review": False,
        }
    )
    decision = RiskEngine(settings).evaluate(
        signal=signal,
        ai_review=review,
        ai_schema_valid=True,
        account=AccountState(equity_usdt=Decimal("1000")),
        position=PositionState(symbol="BTCUSDT"),
        market_health=MarketHealth(reconnecting=True),
        symbol_filters=SymbolFilters(
            symbol="BTCUSDT",
            tick_size=Decimal("0.10"),
            step_size=Decimal("0.001"),
            min_qty=Decimal("0.001"),
            min_notional=Decimal("10"),
        ),
        order_price=Decimal("100.00"),
        order_quantity=Decimal("0.2"),
        trading_mode="testnet",
        client_order_id="id",
    )
    assert decision.approved is False
    assert "reconnecting" in decision.reason

