from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import SecretStr

from account.schemas import AccountSyncStatus, PositionSyncStatus
from account.state_service import AccountPositionService
from broker.base import Broker
from config.settings import load_settings


class FakeBroker(Broker):
    def __init__(self, *, fail: bool = False):
        self.fail = fail

    async def get_account(self):
        if self.fail:
            raise RuntimeError("account unavailable")
        return {
            "balances": [
                {"asset": "USDT", "free": "900", "locked": "100"},
                {"asset": "BTC", "free": "0.01", "locked": "0.00"},
                {"asset": "ETH", "free": "0.5", "locked": "0.1"},
            ]
        }

    async def get_exchange_info(self):
        return {}

    async def get_klines(self, symbol, interval, limit):
        return []

    async def place_order(self, order_request):
        raise AssertionError("AccountPositionService must not place orders")

    async def cancel_order(self, symbol, order_id):
        return {}

    async def get_order(self, symbol, order_id):
        return {}


def _settings_with_keys():
    return load_settings().model_copy(
        update={
            "binance_testnet_api_key": SecretStr("test-key"),
            "binance_testnet_api_secret": SecretStr("test-secret"),
        }
    )


@pytest.mark.asyncio
async def test_get_account_success_parses_balances_and_positions() -> None:
    service = AccountPositionService(
        settings=_settings_with_keys(),
        broker=FakeBroker(),
        dry_run=False,
        order_execution_enabled=True,
    )
    snapshot = await service.refresh_all(
        ["BTCUSDT", "ETHUSDT"],
        {"BTCUSDT": Decimal("100000"), "ETHUSDT": Decimal("2000")},
    )
    assert snapshot.account.status == AccountSyncStatus.OK
    assert snapshot.account.available_usdt == Decimal("900")
    assert snapshot.account.equity_usdt == Decimal("3100.000")
    assert {position.symbol for position in snapshot.positions} == {"BTCUSDT", "ETHUSDT"}
    assert all(position.status == PositionSyncStatus.OK for position in snapshot.positions)


@pytest.mark.asyncio
async def test_get_account_failure_returns_error_without_crashing() -> None:
    service = AccountPositionService(
        settings=_settings_with_keys(),
        broker=FakeBroker(fail=True),
        dry_run=False,
        order_execution_enabled=True,
    )
    account = await service.refresh_account_state()
    assert account.status == AccountSyncStatus.ERROR
    assert account.is_safe_for_real_order is False


@pytest.mark.asyncio
async def test_dry_run_missing_keys_returns_simulated_default() -> None:
    service = AccountPositionService(
        settings=load_settings().model_copy(
            update={"binance_testnet_api_key": None, "binance_testnet_api_secret": None}
        ),
        broker=FakeBroker(),
        dry_run=True,
        order_execution_enabled=False,
    )
    account = await service.refresh_account_state()
    assert account.status == AccountSyncStatus.SIMULATED_DEFAULT
    assert account.source == "simulated_default"


@pytest.mark.asyncio
async def test_latest_price_missing_marks_position_unknown() -> None:
    service = AccountPositionService(
        settings=_settings_with_keys(),
        broker=FakeBroker(),
        dry_run=False,
        order_execution_enabled=True,
    )
    snapshot = await service.refresh_all(["BTCUSDT"], {})
    assert snapshot.positions[0].status == PositionSyncStatus.UNKNOWN
    assert snapshot.positions[0].is_safe_for_real_order is False


@pytest.mark.asyncio
async def test_account_position_snapshot_does_not_leak_secret_strings() -> None:
    service = AccountPositionService(
        settings=_settings_with_keys(),
        broker=FakeBroker(),
        dry_run=False,
        order_execution_enabled=True,
    )
    snapshot = await service.refresh_all(["BTCUSDT"], {"BTCUSDT": Decimal("100000")})
    rendered = json.dumps(snapshot.model_dump(mode="json"))
    assert "test-key" not in rendered
    assert "test-secret" not in rendered
