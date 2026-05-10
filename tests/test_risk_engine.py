from __future__ import annotations

from decimal import Decimal

from ai.schemas import SignalReview
from binance_client.exchange_info import SymbolFilters
from config.settings import load_settings
from risk.risk_engine import AccountState, MarketHealth, PositionState, RiskEngine
from strategies.base import StrategySignalPayload


def _filters() -> SymbolFilters:
    return SymbolFilters(
        symbol="BTCUSDT",
        tick_size=Decimal("0.10"),
        step_size=Decimal("0.001"),
        min_qty=Decimal("0.001"),
        min_notional=Decimal("10"),
    )


def _signal(side: str = "BUY") -> StrategySignalPayload:
    return StrategySignalPayload(
        symbol="BTCUSDT",
        strategy_name="ema_trend",
        strategy_version="v1.0",
        timeframe="5m",
        side=side,
        signal_type="ENTRY_CANDIDATE",
        confidence=0.7,
        reason="test",
        raw_payload_json={},
    )


def _ai() -> SignalReview:
    return SignalReview.model_validate(
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


def _evaluate(**overrides: object):
    settings = overrides.pop("settings", load_settings())
    engine = RiskEngine(settings=settings)
    return engine.evaluate(
        signal=overrides.get("signal", _signal()),
        ai_review=overrides.get("ai_review", _ai()),
        ai_schema_valid=overrides.get("ai_schema_valid", True),
        account=overrides.get(
            "account",
            AccountState(equity_usdt=Decimal("1000"), daily_loss_pct=0, consecutive_losses=0),
        ),
        position=overrides.get("position", PositionState(symbol="BTCUSDT")),
        market_health=overrides.get("market_health", MarketHealth()),
        symbol_filters=_filters(),
        order_price=Decimal("100.00"),
        order_quantity=Decimal("0.200"),
        trading_mode=overrides.get("trading_mode", "testnet"),
        client_order_id=overrides.get("client_order_id", "abc"),
    )


def test_daily_loss_limit_rejects() -> None:
    decision = _evaluate(account=AccountState(equity_usdt=Decimal("1000"), daily_loss_pct=-2.1))
    assert decision.approved is False
    assert "daily loss" in decision.reason


def test_consecutive_losses_rejects() -> None:
    account = AccountState(equity_usdt=Decimal("1000"), consecutive_losses=3)
    assert _evaluate(account=account).approved is False


def test_kill_switch_rejects() -> None:
    settings = load_settings()
    risk = settings.risk_config.model_copy(update={"kill_switch_enabled": True})
    settings = settings.model_copy(update={"risk_config": risk})
    assert _evaluate(settings=settings).approved is False


def test_websocket_disconnect_rejects() -> None:
    decision = _evaluate(market_health=MarketHealth(ws_connected=False))
    assert decision.approved is False
    assert "websocket" in decision.reason


def test_live_disabled_rejects_live_order() -> None:
    settings = load_settings().model_copy(
        update={"trading_mode": "live", "live_trading_enabled": False}
    )
    decision = _evaluate(settings=settings, trading_mode="live")
    assert decision.approved is False
    assert "live" in decision.reason


def test_ai_schema_invalid_rejects() -> None:
    decision = _evaluate(ai_schema_valid=False)
    assert decision.approved is False
    assert "AI schema" in decision.reason
