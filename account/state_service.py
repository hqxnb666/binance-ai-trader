from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from account.schemas import (
    AccountBalanceSnapshot,
    AccountPositionSnapshot,
    AccountSyncStatus,
    PositionSyncStatus,
    RuntimeAccountState,
    RuntimePositionState,
)
from broker.base import Broker
from config.settings import Settings

logger = logging.getLogger(__name__)


class AccountPositionService:
    def __init__(
        self,
        *,
        settings: Settings,
        broker: Broker,
        dry_run: bool,
        order_execution_enabled: bool,
    ):
        self.settings = settings
        self.broker = broker
        self.dry_run = dry_run
        self.order_execution_enabled = order_execution_enabled
        self.latest_account_state: RuntimeAccountState | None = None
        self.latest_position_states: dict[str, RuntimePositionState] = {}
        self.latest_snapshot: AccountPositionSnapshot | None = None

    async def refresh_account_state(self) -> RuntimeAccountState:
        if (
            not self.settings.binance_testnet_api_key
            or not self.settings.binance_testnet_api_secret
        ):
            account = self._simulated_account("missing_testnet_keys")
            self.latest_account_state = account
            return account
        try:
            raw = await self.broker.get_account()
            account = self._account_from_binance(raw)
        except Exception as exc:  # noqa: BLE001 - daemon must not crash on account sync
            logger.warning("account_state_refresh_failed", extra={"error": type(exc).__name__})
            account = (
                self._simulated_account(str(exc)) if self.dry_run else self._error_account(exc)
            )
        self.latest_account_state = account
        return account

    async def get_position_state(
        self,
        symbol: str,
        latest_price: Decimal | None,
    ) -> RuntimePositionState:
        account = self.latest_account_state or await self.refresh_account_state()
        position = self._position_from_account(account, symbol, latest_price)
        self.latest_position_states[symbol.upper()] = position
        return position

    async def refresh_all(
        self,
        symbols: list[str],
        latest_prices: dict[str, Decimal],
    ) -> AccountPositionSnapshot:
        account = await self.refresh_account_state()
        positions = [
            self._position_from_account(account, symbol, latest_prices.get(symbol.upper()))
            for symbol in symbols
        ]
        account = _account_with_position_totals(account, positions)
        positions = [
            self._position_from_account(account, symbol, latest_prices.get(symbol.upper()))
            for symbol in symbols
        ]
        self.latest_position_states = {position.symbol: position for position in positions}
        safe = account.is_safe_for_real_order and all(
            position.is_safe_for_real_order for position in positions
        )
        reason_codes = _snapshot_reason_codes(account, positions)
        snapshot = AccountPositionSnapshot(
            created_at=datetime.now(UTC),
            source=account.source,
            account=account,
            positions=positions,
            safe_for_real_order=safe,
            reason_codes=reason_codes,
        )
        self.latest_snapshot = snapshot
        return snapshot

    def simulated_snapshot(self, symbols: list[str]) -> AccountPositionSnapshot:
        account = self._simulated_account("simulated_default")
        positions = [
            self._position_from_account(account, symbol, Decimal("0")) for symbol in symbols
        ]
        snapshot = AccountPositionSnapshot(
            created_at=datetime.now(UTC),
            source="simulated_default",
            account=account,
            positions=positions,
            safe_for_real_order=False,
            reason_codes=["ACCOUNT_SIMULATED_DEFAULT", "POSITION_SIMULATED_DEFAULT"],
        )
        self.latest_account_state = account
        self.latest_position_states = {position.symbol: position for position in positions}
        self.latest_snapshot = snapshot
        return snapshot

    def _account_from_binance(self, raw: dict[str, Any]) -> RuntimeAccountState:
        balances = _balances(raw)
        usdt = balances.get("USDT", AccountBalanceSnapshot(asset="USDT", free=0, locked=0, total=0))
        usdt_total = _decimal(usdt.total)
        account = RuntimeAccountState(
            created_at=datetime.now(UTC),
            status=AccountSyncStatus.OK,
            source="binance_rest",
            equity_usdt=usdt_total,
            available_usdt=_decimal(usdt.free),
            balances=[item for asset, item in balances.items() if asset in {"BTC", "ETH", "USDT"}],
            daily_realized_pnl="unknown",
            daily_unrealized_pnl="unknown",
            daily_loss_pct=0,
            consecutive_losses=0,
            total_position_pct=0,
            error_message=None,
            is_safe_for_real_order=True,
        )
        return account

    def _position_from_account(
        self,
        account: RuntimeAccountState,
        symbol: str,
        latest_price: Decimal | None,
    ) -> RuntimePositionState:
        symbol = symbol.upper()
        base_asset = symbol.removesuffix("USDT")
        quote_asset = "USDT"
        balance = next(
            (item for item in account.balances if item.asset == base_asset),
            AccountBalanceSnapshot(asset=base_asset, free=0, locked=0, total=0),
        )
        quantity = _decimal(balance.total)
        available = _decimal(balance.free)
        locked = _decimal(balance.locked)
        if account.status in {AccountSyncStatus.SIMULATED_DEFAULT, AccountSyncStatus.UNKNOWN}:
            status = PositionSyncStatus.SIMULATED_DEFAULT
            source = "simulated_default"
            safe = False
            value: Decimal | str = "unknown"
        elif account.status != AccountSyncStatus.OK:
            status = PositionSyncStatus.ERROR
            source = account.source if account.source != "binance_rest" else "unknown"
            safe = False
            value = "unknown"
        elif latest_price is None:
            status = PositionSyncStatus.UNKNOWN
            source = "binance_rest"
            safe = False
            value = "unknown"
        else:
            status = PositionSyncStatus.OK
            source = "binance_rest"
            value = quantity * latest_price
            safe = True
        equity = _decimal(account.equity_usdt)
        value_decimal = _decimal(value)
        position_pct = float((value_decimal / equity) * Decimal("100")) if equity > 0 else 0
        return RuntimePositionState(
            created_at=datetime.now(UTC),
            symbol=symbol,
            status=status,
            source=source,
            base_asset=base_asset,
            quote_asset=quote_asset,
            quantity=quantity,
            available_quantity=available,
            locked_quantity=locked,
            estimated_value_usdt=value,
            entry_price=None,
            unrealized_pnl="unknown",
            position_pct=position_pct,
            side="LONG" if quantity > 0 else "FLAT",
            last_loss_at=None,
            error_message=account.error_message,
            is_safe_for_real_order=safe,
        )

    def _simulated_account(self, reason: str) -> RuntimeAccountState:
        return RuntimeAccountState(
            created_at=datetime.now(UTC),
            status=AccountSyncStatus.SIMULATED_DEFAULT
            if self.dry_run or not self.order_execution_enabled
            else AccountSyncStatus.UNKNOWN,
            source="simulated_default"
            if self.dry_run or not self.order_execution_enabled
            else "unknown",
            equity_usdt=Decimal("1000"),
            available_usdt=Decimal("1000"),
            balances=[
                AccountBalanceSnapshot(
                    asset="USDT",
                    free=Decimal("1000"),
                    locked=0,
                    total=Decimal("1000"),
                ),
                AccountBalanceSnapshot(asset="BTC", free=0, locked=0, total=0),
                AccountBalanceSnapshot(asset="ETH", free=0, locked=0, total=0),
            ],
            daily_realized_pnl="unknown",
            daily_unrealized_pnl="unknown",
            daily_loss_pct=0,
            consecutive_losses=0,
            total_position_pct=0,
            error_message=reason[:300],
            is_safe_for_real_order=False,
        )

    def _error_account(self, exc: Exception) -> RuntimeAccountState:
        return RuntimeAccountState(
            created_at=datetime.now(UTC),
            status=AccountSyncStatus.ERROR,
            source="unknown",
            equity_usdt="unknown",
            available_usdt="unknown",
            balances=[],
            daily_realized_pnl="unknown",
            daily_unrealized_pnl="unknown",
            daily_loss_pct=0,
            consecutive_losses=0,
            total_position_pct=0,
            error_message=str(exc)[:300],
            is_safe_for_real_order=False,
        )


def _balances(raw: dict[str, Any]) -> dict[str, AccountBalanceSnapshot]:
    result: dict[str, AccountBalanceSnapshot] = {}
    for item in raw.get("balances", []):
        asset = str(item.get("asset", "")).upper()
        if not asset:
            continue
        free = _decimal(item.get("free", "0"))
        locked = _decimal(item.get("locked", "0"))
        result[asset] = AccountBalanceSnapshot(
            asset=asset,
            free=free,
            locked=locked,
            total=free + locked,
        )
    return result


def _decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return Decimal("0")


def _snapshot_reason_codes(
    account: RuntimeAccountState, positions: list[RuntimePositionState]
) -> list[str]:
    codes: list[str] = []
    if account.status != AccountSyncStatus.OK:
        codes.append(f"ACCOUNT_{account.status.value}")
    for position in positions:
        if position.status != PositionSyncStatus.OK:
            codes.append(f"POSITION_{position.symbol}_{position.status.value}")
    return codes


def _account_with_position_totals(
    account: RuntimeAccountState, positions: list[RuntimePositionState]
) -> RuntimeAccountState:
    usdt = _decimal(account.available_usdt)
    position_value = sum(
        (_decimal(position.estimated_value_usdt) for position in positions),
        Decimal("0"),
    )
    equity = usdt + position_value
    total_position_pct = float((position_value / equity) * Decimal("100")) if equity > 0 else 0
    return account.model_copy(
        update={
            "equity_usdt": equity,
            "total_position_pct": total_position_pct,
        }
    )
