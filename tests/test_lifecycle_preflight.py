from __future__ import annotations

from pydantic import SecretStr

from config.settings import load_settings
from scripts.testnet_order_lifecycle import validate_lifecycle_safety


def _settings_ready():
    return load_settings().model_copy(
        update={
            "trading_dry_run": False,
            "order_execution_enabled": True,
            "binance_testnet_api_key": SecretStr("k"),
            "binance_testnet_api_secret": SecretStr("s"),
        }
    )


def test_lifecycle_rejects_missing_data_quality_account_position() -> None:
    errors = validate_lifecycle_safety(
        _settings_ready(),
        confirmed=True,
        data_quality_safe_for_real_order=False,
        account_state_status="UNKNOWN",
        position_state_status="UNKNOWN",
    )
    assert any("DataQualityGate" in error for error in errors)
    assert any("Account state" in error for error in errors)
    assert any("Position state" in error for error in errors)


def test_lifecycle_rejects_dry_run_true() -> None:
    settings = _settings_ready().model_copy(update={"trading_dry_run": True})
    errors = validate_lifecycle_safety(
        settings,
        confirmed=True,
        data_quality_safe_for_real_order=True,
        account_state_status="OK",
        position_state_status="OK",
    )
    assert any("TRADING_DRY_RUN" in error for error in errors)


def test_lifecycle_rejects_live_enabled() -> None:
    settings = _settings_ready().model_copy(update={"live_trading_enabled": True})
    errors = validate_lifecycle_safety(
        settings,
        confirmed=True,
        data_quality_safe_for_real_order=True,
        account_state_status="OK",
        position_state_status="OK",
    )
    assert any("Live trading" in error for error in errors)


def test_lifecycle_rejects_order_execution_disabled() -> None:
    settings = _settings_ready().model_copy(update={"order_execution_enabled": False})
    errors = validate_lifecycle_safety(
        settings,
        confirmed=True,
        data_quality_safe_for_real_order=True,
        account_state_status="OK",
        position_state_status="OK",
    )
    assert any("ORDER_EXECUTION_ENABLED" in error for error in errors)


def test_lifecycle_preflight_can_pass_before_manual_risk_decision() -> None:
    errors = validate_lifecycle_safety(
        _settings_ready(),
        confirmed=True,
        data_quality_safe_for_real_order=True,
        account_state_status="OK",
        position_state_status="OK",
        runtime_kill_switch_enabled=False,
    )
    assert errors == []
