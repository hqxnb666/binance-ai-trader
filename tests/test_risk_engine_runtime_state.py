from __future__ import annotations

from decimal import Decimal

from ai.schemas import SignalReview
from binance_client.exchange_info import SymbolFilters
from config.settings import load_settings
from risk.risk_engine import AccountState, MarketHealth, PositionState, RiskEngine
from strategies.base import StrategySignalPayload


def _filters() -> SymbolFilters:
    return SymbolFilters(
        "BTCUSDT",
        Decimal("0.1"),
        Decimal("0.001"),
        Decimal("0.001"),
        Decimal("10"),
    )


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


def _evaluate(engine: RiskEngine, client_order_id: str):
    return engine.evaluate(
        signal=_signal(),
        ai_review=_review(),
        ai_schema_valid=True,
        account=AccountState(equity_usdt=Decimal("1000")),
        position=PositionState(symbol="BTCUSDT"),
        market_health=MarketHealth(),
        symbol_filters=_filters(),
        order_price=Decimal("100.0"),
        order_quantity=Decimal("0.2"),
        trading_mode="testnet",
        client_order_id=client_order_id,
    )


def test_reused_risk_engine_accumulates_order_frequency_state() -> None:
    engine = RiskEngine(load_settings())
    assert _evaluate(engine, "id-1").approved is True
    assert _evaluate(engine, "id-2").approved is True
    assert engine.runtime_state()["orders_last_minute"] == 2
    assert engine.runtime_state()["seen_client_order_id_count"] == 2


def test_duplicate_client_order_id_is_rejected() -> None:
    engine = RiskEngine(load_settings())
    assert _evaluate(engine, "same-id").approved is True
    duplicate = _evaluate(engine, "same-id")
    assert duplicate.approved is False
    assert "duplicate" in duplicate.reason


def test_runtime_kill_switch_rejects() -> None:
    engine = RiskEngine(load_settings())
    decision = engine.evaluate(
        signal=_signal(),
        ai_review=_review(),
        ai_schema_valid=True,
        account=AccountState(equity_usdt=Decimal("1000")),
        position=PositionState(symbol="BTCUSDT"),
        market_health=MarketHealth(),
        symbol_filters=_filters(),
        order_price=Decimal("100.0"),
        order_quantity=Decimal("0.2"),
        trading_mode="testnet",
        client_order_id="kill",
        runtime_kill_switch_enabled=True,
    )
    assert decision.approved is False
    assert decision.reason == "runtime kill switch enabled"


def test_config_kill_switch_still_rejects() -> None:
    settings = load_settings()
    settings = settings.model_copy(
        update={
            "risk_config": settings.risk_config.model_copy(
                update={"kill_switch_enabled": True}
            )
        }
    )
    decision = _evaluate(RiskEngine(settings), "config-kill")
    assert decision.approved is False
    assert decision.reason == "kill switch enabled"
