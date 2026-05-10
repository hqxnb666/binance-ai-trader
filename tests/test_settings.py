from __future__ import annotations

from config.settings import load_settings


def test_live_defaults_disabled() -> None:
    settings = load_settings()
    assert settings.trading_mode == "testnet"
    assert settings.live_trading_enabled is False
    assert settings.live_trading.enabled is False
    assert settings.trading_dry_run is True
    assert settings.order_execution_enabled is False


def test_safe_config_does_not_expose_api_keys() -> None:
    safe = load_settings().safe_config()
    rendered = str(safe)
    assert "BINANCE_TESTNET_API_SECRET" not in rendered
    assert "BINANCE_LIVE_API_SECRET" not in rendered
    assert "OPENAI_API_KEY" not in rendered
    assert "your_testnet" not in rendered
    assert "has_testnet_key" in safe["binance"]
