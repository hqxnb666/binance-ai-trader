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


def test_shadow_attribution_defaults_are_diagnostic_only() -> None:
    settings = load_settings()
    assert settings.shadow_attribution_enabled is True
    assert settings.shadow_attribution_evaluate_beyond_strategy_plan is True
    assert settings.shadow_attribution_max_records_per_cycle == 10
    safe = settings.safe_config()["shadow_mode"]
    assert safe["attribution_enabled"] is True
    assert safe["attribution_evaluate_beyond_strategy_plan"] is True
