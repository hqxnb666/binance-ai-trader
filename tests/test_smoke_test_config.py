from __future__ import annotations

import pytest

from config.settings import load_settings
from scripts.smoke_test_testnet import build_preflight_report, smoke_test


def test_smoke_preflight_report_is_clear_without_keys() -> None:
    report = build_preflight_report(load_settings())
    assert "has_binance_testnet_key" in report
    assert "order_execution_enabled" in report
    assert report["live_trading_enabled"] is False


@pytest.mark.asyncio
async def test_smoke_config_only_does_not_require_api_keys() -> None:
    report = await smoke_test(check_config_only=True)
    assert report["status"] == "CONFIG_ONLY"
    assert "stages" in report
    assert report["stages"][0]["name"] == "Stage 0: Config check"

