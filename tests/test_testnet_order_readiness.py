from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import SecretStr

import scripts.verify_testnet_order_readiness as readiness
from account.schemas import (
    AccountPositionSnapshot,
    AccountSyncStatus,
    RuntimeAccountState,
    RuntimePositionState,
)
from config.settings import load_settings


class FakeService:
    def __init__(self, *args, account_status: AccountSyncStatus = AccountSyncStatus.OK, **kwargs):
        self.account_status = account_status

    async def refresh_all(self, symbols, latest_prices):
        account = RuntimeAccountState(
            created_at=datetime.now(UTC),
            status=self.account_status,
            source="binance_rest" if self.account_status == AccountSyncStatus.OK else "unknown",
            equity_usdt=Decimal("1000")
            if self.account_status == AccountSyncStatus.OK
            else "unknown",
            available_usdt=Decimal("1000")
            if self.account_status == AccountSyncStatus.OK
            else "unknown",
            balances=[],
            daily_realized_pnl="unknown",
            daily_unrealized_pnl="unknown",
            daily_loss_pct=0,
            consecutive_losses=0,
            total_position_pct=0,
            error_message=None,
            is_safe_for_real_order=self.account_status == AccountSyncStatus.OK,
        )
        positions = [
            RuntimePositionState(
                created_at=datetime.now(UTC),
                symbol=symbol,
                status="OK" if self.account_status == AccountSyncStatus.OK else "UNKNOWN",
                source="binance_rest" if self.account_status == AccountSyncStatus.OK else "unknown",
                base_asset=symbol.removesuffix("USDT"),
                quote_asset="USDT",
                quantity=0,
                available_quantity=0,
                locked_quantity=0,
                estimated_value_usdt=0,
                position_pct=0,
                side="FLAT",
                is_safe_for_real_order=self.account_status == AccountSyncStatus.OK,
            )
            for symbol in symbols
        ]
        return AccountPositionSnapshot(
            created_at=datetime.now(UTC),
            source=account.source,
            account=account,
            positions=positions,
            safe_for_real_order=account.is_safe_for_real_order,
            reason_codes=[] if account.is_safe_for_real_order else ["ACCOUNT_UNKNOWN"],
        )


async def _fake_rest_ok(broker, settings, report):
    return {"rest_ok": True, "filters_ok": True}, {"BTCUSDT": Decimal("100000")}


@pytest.mark.asyncio
async def test_readiness_json_shape_no_keys(monkeypatch) -> None:
    monkeypatch.setattr(readiness, "_check_rest_and_filters", _fake_rest_ok)
    monkeypatch.setattr(readiness, "AccountPositionService", FakeService)
    settings = load_settings().model_copy(
        update={"binance_testnet_api_key": None, "binance_testnet_api_secret": None}
    )
    report = await readiness.build_readiness_report(settings)
    rendered = json.dumps(report)
    assert report["ready_for_real_testnet_order"] is False
    assert report["ready_for_live"] is False
    assert "API_KEY" not in rendered


@pytest.mark.asyncio
async def test_dry_run_can_be_ready_for_dry_run(monkeypatch) -> None:
    monkeypatch.setattr(readiness, "_check_rest_and_filters", _fake_rest_ok)
    monkeypatch.setattr(readiness, "AccountPositionService", FakeService)
    report = await readiness.build_readiness_report(load_settings())
    assert report["ready_for_dry_run"] is True
    assert report["ready_for_real_testnet_order"] is False


@pytest.mark.asyncio
async def test_kill_switch_blocks_real_readiness(monkeypatch) -> None:
    monkeypatch.setattr(readiness, "_check_rest_and_filters", _fake_rest_ok)
    monkeypatch.setattr(readiness, "AccountPositionService", FakeService)
    settings = load_settings().model_copy(
        update={
            "trading_dry_run": False,
            "order_execution_enabled": True,
            "binance_testnet_api_key": SecretStr("k"),
            "binance_testnet_api_secret": SecretStr("s"),
            "risk_config": load_settings().risk_config.model_copy(
                update={"kill_switch_enabled": True}
            ),
        }
    )
    report = await readiness.build_readiness_report(settings)
    assert report["ready_for_real_testnet_order"] is False
    assert "Kill switch is enabled" in report["blockers"]


@pytest.mark.asyncio
async def test_account_unknown_blocks_real_readiness(monkeypatch) -> None:
    monkeypatch.setattr(readiness, "_check_rest_and_filters", _fake_rest_ok)

    class UnknownService(FakeService):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, account_status=AccountSyncStatus.UNKNOWN, **kwargs)

    monkeypatch.setattr(readiness, "AccountPositionService", UnknownService)
    settings = load_settings().model_copy(
        update={
            "trading_dry_run": False,
            "order_execution_enabled": True,
            "binance_testnet_api_key": SecretStr("k"),
            "binance_testnet_api_secret": SecretStr("s"),
        }
    )
    report = await readiness.build_readiness_report(settings)
    assert report["ready_for_real_testnet_order"] is False
    assert "Account state is not OK" in report["blockers"]
