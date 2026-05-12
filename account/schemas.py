from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AccountSyncStatus(StrEnum):
    OK = "OK"
    UNKNOWN = "UNKNOWN"
    SIMULATED_DEFAULT = "SIMULATED_DEFAULT"
    ERROR = "ERROR"
    STALE = "STALE"


class PositionSyncStatus(StrEnum):
    OK = "OK"
    UNKNOWN = "UNKNOWN"
    SIMULATED_DEFAULT = "SIMULATED_DEFAULT"
    ERROR = "ERROR"
    STALE = "STALE"


class AccountBalanceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str
    free: Decimal | str
    locked: Decimal | str
    total: Decimal | str

    @field_validator("asset")
    @classmethod
    def uppercase_asset(cls, value: str) -> str:
        return value.upper()


class RuntimeAccountState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["runtime_account_state_v1"] = "runtime_account_state_v1"
    created_at: datetime
    status: AccountSyncStatus
    source: Literal[
        "binance_rest",
        "user_stream",
        "journal",
        "simulated_default",
        "dry_run_flat_profile",
        "unknown",
    ]
    equity_usdt: Decimal | str
    available_usdt: Decimal | str
    balances: list[AccountBalanceSnapshot] = Field(default_factory=list)
    daily_realized_pnl: Decimal | str | None = None
    daily_unrealized_pnl: Decimal | str | None = None
    daily_loss_pct: float = 0
    consecutive_losses: int = 0
    total_position_pct: float = 0
    error_message: str | None = None
    is_safe_for_real_order: bool = False


class RuntimePositionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["runtime_position_state_v1"] = "runtime_position_state_v1"
    created_at: datetime
    symbol: str
    status: PositionSyncStatus
    source: Literal[
        "binance_rest",
        "user_stream",
        "journal",
        "simulated_default",
        "dry_run_flat_profile",
        "unknown",
    ]
    base_asset: str
    quote_asset: str
    quantity: Decimal | str
    available_quantity: Decimal | str
    locked_quantity: Decimal | str
    estimated_value_usdt: Decimal | str
    entry_price: Decimal | str | None = None
    unrealized_pnl: Decimal | str | None = None
    position_pct: float = 0
    side: Literal["LONG", "FLAT"] = "FLAT"
    last_loss_at: datetime | None = None
    error_message: str | None = None
    is_safe_for_real_order: bool = False

    @field_validator("symbol", "base_asset", "quote_asset")
    @classmethod
    def uppercase_symbol(cls, value: str) -> str:
        return value.upper()


class AccountPositionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["account_position_snapshot_v1"] = "account_position_snapshot_v1"
    created_at: datetime
    source: Literal[
        "binance_rest",
        "user_stream",
        "journal",
        "simulated_default",
        "dry_run_flat_profile",
        "unknown",
    ]
    account: RuntimeAccountState
    positions: list[RuntimePositionState]
    safe_for_real_order: bool
    reason_codes: list[str]
