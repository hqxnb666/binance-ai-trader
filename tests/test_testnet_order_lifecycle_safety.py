from __future__ import annotations

from config.settings import load_settings
from scripts.testnet_order_lifecycle import validate_lifecycle_safety


def test_lifecycle_requires_confirmation_flag() -> None:
    settings = load_settings().model_copy(update={"order_execution_enabled": True})
    errors = validate_lifecycle_safety(settings, confirmed=False)
    assert any("confirmation" in error for error in errors)


def test_lifecycle_rejects_order_execution_disabled() -> None:
    settings = load_settings().model_copy(update={"order_execution_enabled": False})
    errors = validate_lifecycle_safety(settings, confirmed=True)
    assert any("ORDER_EXECUTION_ENABLED" in error for error in errors)

